"""Quiz generation, submission, wrong answers, and Anki export."""

import csv
import io
import json
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.db.database import get_db
from app.dependencies import get_rag_pipeline
from app.models.schemas import (
    QuizGenerateRequest,
    QuizQuestionResponse,
    QuizResponse,
    QuizResultItem,
    QuizResultResponse,
    QuizSubmitRequest,
    WrongAnswerResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/quiz", tags=["quiz"])


def _escape_like(s: str) -> str:
    """Escape special characters in LIKE patterns (% and _)."""
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# -- Generate Quiz -------------------------------------------------


@router.post("/generate", response_model=QuizResponse)
async def generate_quiz(request: QuizGenerateRequest):
    """Generate a quiz using LLM based on document content."""
    pipeline = get_rag_pipeline()
    with get_db() as conn:
        # Gather document content for quiz generation
        if request.doc_ids:
            placeholders = ",".join("?" for _ in request.doc_ids)
            docs = conn.execute(
                f"SELECT id, filename FROM documents WHERE id IN ({placeholders}) AND status='ready'",
                request.doc_ids,
            ).fetchall()
        elif request.tag:
            docs = conn.execute(
                """SELECT d.id, d.filename FROM documents d
                   JOIN document_tags dt ON dt.doc_id = d.id
                   JOIN tags t ON t.id = dt.tag_id
                   WHERE t.name = ? AND d.status = 'ready'""",
                (request.tag,),
            ).fetchall()
        else:
            docs = conn.execute(
                "SELECT id, filename FROM documents WHERE status='ready' LIMIT 5"
            ).fetchall()

        if not docs:
            raise HTTPException(
                status_code=400, detail="No documents available for quiz (need status=ready)"
            )

        # Gather chunks from these documents (include chunk id for tracking)
        doc_ids = [d["id"] for d in docs]
        placeholders = ",".join("?" for _ in doc_ids)
        chunks = conn.execute(
            f"SELECT id, text, doc_id FROM chunks WHERE doc_id IN ({placeholders}) ORDER BY RANDOM() LIMIT 10",
            doc_ids,
        ).fetchall()

        if not chunks:
            raise HTTPException(
                status_code=400, detail="No content available in documents for quiz generation"
            )

        # Build context from chunks (with chunk_id map for source tracking)
        chunk_id_map: dict[int, str] = {}
        context_parts: list[str] = []
        for i, c in enumerate(chunks):
            chunk_id_map[i + 1] = c["id"]
            context_parts.append(f"[{i + 1}] {c['text'][:500]}")
        context = "\n\n".join(context_parts)[:4000]

        # Ask LLM to generate quiz
        count = min(request.count, 10)
        quiz_response = await pipeline.generator.client.chat.completions.create(
            model=pipeline.generator.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a quiz generation expert. Generate quiz questions based on the provided learning materials.\n"
                        "Requirements:\n"
                        f"- Generate {count} questions\n"
                        "- Mix choice questions and true_false questions\n"
                        "- Choice questions must have exactly 4 options\n"
                        "- Every question must have an explanation\n"
                        '- Include a "source_chunk_index" field (integer) indicating which [N] source chunk the question is based on\n'
                        "- Output strictly in the following JSON format, no extra text:\n"
                        '{"questions": [{"type": "choice"|"true_false", "question": "question text", '
                        '"options": ["A option","B option","C option","D option"], '
                        '"answer": "correct answer (for choice use letter A/B/C/D, for true_false use true/false)", '
                        '"explanation": "explanation", "source_chunk_index": N}]}'
                    ),
                },
                {"role": "user", "content": f"Materials:\n{context}"},
            ],
            temperature=0.7,
        )

        raw_text = quiz_response.choices[0].message.content or ""
        logger.info("LLM raw quiz response: %s", raw_text[:200])

        # Parse JSON from LLM response
        try:
            # Try to extract JSON from markdown code blocks if present
            if "```json" in raw_text:
                json_str = raw_text.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_text:
                json_str = raw_text.split("```")[1].split("```")[0].strip()
            else:
                json_str = raw_text.strip()

            quiz_data = json.loads(json_str)
            questions_raw = quiz_data.get("questions", [])
        except (json.JSONDecodeError, IndexError) as e:
            logger.error("Failed to parse quiz JSON: %s, raw: %s", e, raw_text[:300])
            raise HTTPException(
                status_code=500, detail="LLM generated invalid quiz format, please retry"
            ) from e

        if not questions_raw:
            raise HTTPException(status_code=500, detail="LLM generated no questions, please retry")

        # Save quiz to DB
        quiz_id = str(uuid.uuid4())
        topic = ", ".join(d["filename"] for d in docs[:3])
        conn.execute(
            "INSERT INTO quizzes (id, topic, doc_ids, tag, total_count) VALUES (?, ?, ?, ?, ?)",
            (quiz_id, topic, json.dumps(doc_ids), request.tag, len(questions_raw)),
        )

        question_responses = []
        for q in questions_raw:
            q_id = str(uuid.uuid4())
            q_type = q.get("type", "choice")
            q_text = q.get("question", "")
            q_options = (
                json.dumps(q.get("options", []), ensure_ascii=False) if q.get("options") else None
            )
            q_answer = q.get("answer", "")
            q_explanation = q.get("explanation", "")
            # Map LLM-returned source_chunk_index to actual chunk_id
            q_source_chunk_idx = q.get("source_chunk_index")
            q_source_chunk_id = (
                chunk_id_map.get(q_source_chunk_idx)
                if isinstance(q_source_chunk_idx, int)
                else None
            )

            conn.execute(
                """INSERT INTO quiz_questions
                   (id, quiz_id, question_type, question_text, options, correct_answer, explanation, source_chunk_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    q_id,
                    quiz_id,
                    q_type,
                    q_text,
                    q_options,
                    q_answer,
                    q_explanation,
                    q_source_chunk_id,
                ),
            )

            question_responses.append(
                QuizQuestionResponse(
                    id=q_id,
                    question_type=q_type,
                    question_text=q_text,
                    options=q.get("options") if q_type == "choice" else None,
                )
            )

        conn.commit()

        return QuizResponse(
            id=quiz_id,
            topic=topic,
            total_count=len(question_responses),
            questions=question_responses,
            created_at=datetime.now().isoformat(),
        )


# -- Submit Quiz ---------------------------------------------------


@router.post("/{quiz_id}/submit", response_model=QuizResultResponse)
async def submit_quiz(quiz_id: str, request: QuizSubmitRequest):
    """Submit quiz answers and get results."""
    with get_db() as conn:
        quiz = conn.execute("SELECT * FROM quizzes WHERE id=?", (quiz_id,)).fetchone()
        if not quiz:
            raise HTTPException(status_code=404, detail="Quiz not found")

        results = []
        correct_count = 0

        # Batch-fetch all questions at once (fixes N+1: was 1 query per answer)
        answer_ids = [ans.get("question_id", "") for ans in request.answers]
        if not answer_ids:
            raise HTTPException(status_code=400, detail="没有提交任何答案")

        placeholders = ",".join("?" for _ in answer_ids)
        question_rows = conn.execute(
            f"SELECT * FROM quiz_questions WHERE id IN ({placeholders})",
            answer_ids,
        ).fetchall()
        questions_map = {r["id"]: r for r in question_rows}

        # Batch-fetch documents for knowledge points (single query)
        source_chunk_ids = [
            questions_map[ans.get("question_id", "")].get("source_chunk_id")
            for ans in request.answers
            if ans.get("question_id", "") in questions_map
            and questions_map[ans.get("question_id", "")].get("source_chunk_id")
        ]
        doc_map = {}
        if source_chunk_ids:
            sc_placeholders = ",".join("?" for _ in source_chunk_ids)
            doc_rows = conn.execute(
                f"""SELECT d.id, c.id as chunk_id FROM documents d
                    JOIN chunks c ON c.doc_id = d.id
                    WHERE c.id IN ({sc_placeholders})""",
                source_chunk_ids,
            ).fetchall()
            doc_map = {r["chunk_id"]: r["id"] for r in doc_rows}

        # Batch-fetch existing knowledge points
        kp_names = [
            questions_map[ans.get("question_id", "")]["question_text"][:80]
            for ans in request.answers
            if ans.get("question_id", "") in questions_map
        ]
        kp_map = {}
        if kp_names:
            kp_placeholders = ",".join("?" for _ in kp_names)
            kp_rows = conn.execute(
                f"SELECT id, name, mastery_score, quiz_count, correct_count FROM knowledge_points WHERE name IN ({kp_placeholders})",
                kp_names,
            ).fetchall()
            kp_map = {r["name"]: r for r in kp_rows}

        # Prepare batch inserts
        answer_inserts = []
        wrong_answer_inserts = []
        kp_updates = []
        kp_inserts = []

        for ans in request.answers:
            q_id = ans.get("question_id", "")
            user_answer = ans.get("user_answer", "")

            question = questions_map.get(q_id)
            if not question:
                continue

            is_correct = user_answer.strip().lower() == question["correct_answer"].strip().lower()
            if is_correct:
                correct_count += 1

            results.append(
                QuizResultItem(
                    question_id=q_id,
                    question_text=question["question_text"],
                    user_answer=user_answer,
                    correct_answer=question["correct_answer"],
                    is_correct=is_correct,
                    explanation=question["explanation"],
                )
            )

            # Batch answer insert
            answer_inserts.append(
                (str(uuid.uuid4()), quiz_id, q_id, user_answer, 1 if is_correct else 0)
            )

            # Batch wrong answer insert
            if not is_correct:
                wrong_answer_inserts.append(
                    (
                        str(uuid.uuid4()),
                        q_id,
                        quiz_id,
                        question["question_text"],
                        question["question_type"],
                        question["options"],
                        question["correct_answer"],
                        question["explanation"],
                        user_answer,
                    )
                )

            # Track knowledge point updates
            source_chunk_id = question.get("source_chunk_id")
            if source_chunk_id and source_chunk_id in doc_map:
                kp_name = question["question_text"][:80]
                existing_kp = kp_map.get(kp_name)

                if existing_kp:
                    new_total = existing_kp["quiz_count"] + 1
                    new_correct = existing_kp["correct_count"] + (1 if is_correct else 0)
                    new_score = new_correct / new_total
                    kp_updates.append((new_score, new_total, new_correct, existing_kp["id"]))
                    # Update local cache for subsequent same-name questions
                    kp_map[kp_name] = {
                        **existing_kp,
                        "quiz_count": new_total,
                        "correct_count": new_correct,
                    }
                else:
                    new_id = str(uuid.uuid4())
                    kp_inserts.append(
                        (
                            new_id,
                            doc_map[source_chunk_id],
                            kp_name,
                            1.0 if is_correct else 0.0,
                            1,
                            1 if is_correct else 0,
                        )
                    )
                    kp_map[kp_name] = {
                        "id": new_id,
                        "quiz_count": 1,
                        "correct_count": 1 if is_correct else 0,
                    }

        # Execute batch inserts
        if answer_inserts:
            conn.executemany(
                "INSERT INTO quiz_answers (id, quiz_id, question_id, user_answer, is_correct) VALUES (?, ?, ?, ?, ?)",
                answer_inserts,
            )
        if wrong_answer_inserts:
            conn.executemany(
                """INSERT INTO wrong_answers
                   (id, question_id, quiz_id, question_text, question_type, options,
                    correct_answer, explanation, user_answer)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                wrong_answer_inserts,
            )
        if kp_updates:
            conn.executemany(
                "UPDATE knowledge_points SET mastery_score=?, quiz_count=?, correct_count=? WHERE id=?",
                kp_updates,
            )
        if kp_inserts:
            conn.executemany(
                """INSERT INTO knowledge_points
                   (id, doc_id, name, mastery_score, quiz_count, correct_count)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                kp_inserts,
            )

        # Update quiz status
        conn.execute(
            "UPDATE quizzes SET correct_count=?, status='completed' WHERE id=?",
            (correct_count, quiz_id),
        )
        conn.commit()

        return QuizResultResponse(
            quiz_id=quiz_id,
            correct_count=correct_count,
            total_count=len(results),
            results=results,
        )


# -- Wrong Answers -------------------------------------------------


@router.get("/wrong-answers", response_model=list[WrongAnswerResponse])
async def list_wrong_answers():
    """List all wrong answers for review."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM wrong_answers ORDER BY mastery_level ASC, created_at DESC LIMIT 500"
        ).fetchall()
        return [
            WrongAnswerResponse(
                id=r["id"],
                question_text=r["question_text"],
                question_type=r["question_type"],
                options=json.loads(r["options"]) if r["options"] else None,
                correct_answer=r["correct_answer"],
                explanation=r["explanation"],
                user_answer=r["user_answer"],
                review_count=r["review_count"],
                mastery_level=r["mastery_level"],
                created_at=str(r["created_at"]),
            )
            for r in rows
        ]


@router.post("/wrong-answers/{answer_id}/review")
async def review_wrong_answer(answer_id: str, is_correct: bool):
    """Mark a wrong answer as reviewed (correct or still wrong)."""
    with get_db() as conn:
        wa = conn.execute("SELECT * FROM wrong_answers WHERE id=?", (answer_id,)).fetchone()
        if not wa:
            raise HTTPException(status_code=404, detail="Wrong answer not found")

        new_review_count = wa["review_count"] + 1
        if is_correct:
            new_mastery = min(wa["mastery_level"] + 1, 5)
        else:
            new_mastery = max(wa["mastery_level"] - 1, 0)

        conn.execute(
            """UPDATE wrong_answers
               SET review_count=?, mastery_level=?, last_reviewed=CURRENT_TIMESTAMP
               WHERE id=?""",
            (new_review_count, new_mastery, answer_id),
        )
        conn.commit()

        # Remove from wrong answers if mastery reaches 5
        if new_mastery >= 5:
            conn.execute("DELETE FROM wrong_answers WHERE id=?", (answer_id,))
            conn.commit()

        return {
            "review_count": new_review_count,
            "mastery_level": new_mastery,
            "removed": new_mastery >= 5,
        }


# -- Anki Export ---------------------------------------------------


@router.get("/anki/export")
async def export_to_anki(tag: str | None = None, doc_id: str | None = None):
    """Export quiz questions as Anki-compatible CSV."""
    with get_db() as conn:
        # Gather questions from quizzes (optionally filtered)
        if doc_id:
            questions = conn.execute(
                """SELECT qq.*, q.topic FROM quiz_questions qq
                   JOIN quizzes q ON q.id = qq.quiz_id
                   WHERE q.doc_ids LIKE ?""",
                (f"%{_escape_like(doc_id)}%",),
            ).fetchall()
        elif tag:
            questions = conn.execute(
                """SELECT qq.*, q.topic FROM quiz_questions qq
                   JOIN quizzes q ON q.id = qq.quiz_id
                   WHERE q.tag = ?""",
                (tag,),
            ).fetchall()
        else:
            questions = conn.execute(
                "SELECT qq.*, q.topic FROM quiz_questions qq JOIN quizzes q ON q.id = qq.quiz_id"
            ).fetchall()

        if not questions:
            raise HTTPException(status_code=400, detail="No questions to export")

        # Build CSV
        output = io.StringIO()
        writer = csv.writer(output, delimiter="\t")
        # Anki basic format: Front, Back, Tags
        for q in questions:
            front = q["question_text"]
            if q["question_type"] == "choice" and q["options"]:
                options = json.loads(q["options"])
                front += "\n" + "\n".join(f"{chr(65 + i)}. {opt}" for i, opt in enumerate(options))

            back = f"答案：{q['correct_answer']}"
            if q["explanation"]:
                back += f"\n\n解析：{q['explanation']}"

            try:
                tags = q["topic"] or ""
            except (IndexError, KeyError):
                tags = ""
            tags = tags.replace(" ", "_").replace(",", " ")

            writer.writerow([front, back, tags])

        csv_content = output.getvalue()
        buffer = io.BytesIO(csv_content.encode("utf-8"))

        return StreamingResponse(
            buffer,
            media_type="text/tab-separated-values; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=anki-export.txt"},
        )


# -- Dashboard -----------------------------------------------------


@router.get("/dashboard")
async def get_dashboard():
    """Get learning dashboard statistics."""
    with get_db() as conn:
        total_docs = conn.execute(
            "SELECT COUNT(*) as c FROM documents WHERE status='ready'"
        ).fetchone()["c"]
        total_chunks = conn.execute("SELECT COUNT(*) as c FROM chunks").fetchone()["c"]
        total_questions = conn.execute(
            "SELECT COUNT(*) as c FROM chat_messages WHERE role='user'"
        ).fetchone()["c"]
        total_quizzes = conn.execute("SELECT COUNT(*) as c FROM quizzes").fetchone()["c"]

        # Tag statistics (single query replaces N+1 loop)
        tag_stats = []
        tag_rows = conn.execute(
            """SELECT t.name,
                      COUNT(DISTINCT dt.doc_id) as doc_count,
                      COUNT(DISTINCT cm.id) as question_count
               FROM tags t
               LEFT JOIN document_tags dt ON dt.tag_id = t.id
               LEFT JOIN chat_messages cm ON cm.role = 'user'
               GROUP BY t.id, t.name"""
        ).fetchall()
        for t in tag_rows:
            tag_stats.append(
                {
                    "tag": t["name"],
                    "doc_count": t["doc_count"],
                    "question_count": t["question_count"],
                }
            )

        # Weak points (knowledge points with low mastery)
        weak_points = []
        kp_rows = conn.execute(
            "SELECT name, mastery_score FROM knowledge_points ORDER BY mastery_score ASC LIMIT 10"
        ).fetchall()
        for kp in kp_rows:
            weak_points.append(
                {
                    "concept": kp["name"],
                    "mastery_score": kp["mastery_score"],
                }
            )

        # Recent activity (last 7 days — single query replaces 7 individual queries)
        activity_rows = conn.execute(
            """SELECT
               CAST(julianday('now') - julianday(DATE(created_at)) AS INTEGER) as day_offset,
               COUNT(CASE WHEN role='user' THEN 1 END) as questions,
               COUNT(DISTINCT CASE WHEN role='user' THEN session_id END) as sessions
               FROM chat_messages
               WHERE created_at >= DATE('now', '-6 days')
               GROUP BY DATE(created_at)
               ORDER BY day_offset"""
        ).fetchall()
        activity_map = {r["day_offset"]: r for r in activity_rows}
        recent_activity = [
            {
                "date": f"-{i}d",
                "questions_count": activity_map[i]["questions"] if i in activity_map else 0,
                "sessions": activity_map[i]["sessions"] if i in activity_map else 0,
            }
            for i in range(7)
        ]

        # Quiz stats
        quiz_stats = conn.execute(
            """SELECT COUNT(*) as total,
               SUM(correct_count) as total_correct,
               SUM(total_count) as total_questions
               FROM quizzes WHERE status='completed'"""
        ).fetchone()

        wrong_count = conn.execute("SELECT COUNT(*) as c FROM wrong_answers").fetchone()["c"]

        return {
            "total_documents": total_docs,
            "total_chunks": total_chunks,
            "total_questions_asked": total_questions,
            "total_quizzes": total_quizzes,
            "total_correct_answers": quiz_stats["total_correct"] or 0,
            "wrong_answer_count": wrong_count,
            "tag_stats": tag_stats,
            "weak_points": weak_points,
            "recent_activity": recent_activity,
        }
