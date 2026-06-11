"""Quiz generation, submission, wrong answers, and Anki export."""

import csv
import io
import json
import uuid
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.db.database import get_connection
from app.models.schemas import (
    QuizGenerateRequest,
    QuizResponse,
    QuizQuestionResponse,
    QuizSubmitRequest,
    QuizResultResponse,
    QuizResultItem,
    WrongAnswerResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/quiz", tags=["quiz"])


def _get_rag_pipeline():
    from app.main import rag_pipeline
    return rag_pipeline


# -- Generate Quiz -------------------------------------------------

@router.post("/generate", response_model=QuizResponse)
async def generate_quiz(request: QuizGenerateRequest):
    """Generate a quiz using LLM based on document content."""
    pipeline = _get_rag_pipeline()
    conn = get_connection()

    try:
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
            raise HTTPException(status_code=400, detail="No documents available for quiz (need status=ready)")

        # Gather chunks from these documents
        doc_ids = [d["id"] for d in docs]
        placeholders = ",".join("?" for _ in doc_ids)
        chunks = conn.execute(
            f"SELECT text, doc_id FROM chunks WHERE doc_id IN ({placeholders}) ORDER BY RANDOM() LIMIT 10",
            doc_ids,
        ).fetchall()

        if not chunks:
            raise HTTPException(status_code=400, detail="No content available in documents for quiz generation")

        # Build context from chunks
        context = "\n\n".join(
            f"[{i+1}] {c['text'][:500]}" for i, c in enumerate(chunks)
        )[:4000]

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
                        "- Output strictly in the following JSON format, no extra text:\n"
                        '{"questions": [{"type": "choice"|"true_false", "question": "question text", '
                        '"options": ["A option","B option","C option","D option"], '
                        '"answer": "correct answer (for choice use letter A/B/C/D, for true_false use true/false)", '
                        '"explanation": "explanation"}]}'
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
            raise HTTPException(status_code=500, detail="LLM generated invalid quiz format, please retry")

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
            q_options = json.dumps(q.get("options", []), ensure_ascii=False) if q.get("options") else None
            q_answer = q.get("answer", "")
            q_explanation = q.get("explanation", "")

            conn.execute(
                """INSERT INTO quiz_questions
                   (id, quiz_id, question_type, question_text, options, correct_answer, explanation)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (q_id, quiz_id, q_type, q_text, q_options, q_answer, q_explanation),
            )

            question_responses.append(QuizQuestionResponse(
                id=q_id,
                question_type=q_type,
                question_text=q_text,
                options=q.get("options") if q_type == "choice" else None,
            ))

        conn.commit()

        return QuizResponse(
            id=quiz_id,
            topic=topic,
            total_count=len(question_responses),
            questions=question_responses,
            created_at=datetime.now().isoformat(),
        )
    finally:
        conn.close()


# -- Submit Quiz ---------------------------------------------------

@router.post("/{quiz_id}/submit", response_model=QuizResultResponse)
async def submit_quiz(quiz_id: str, request: QuizSubmitRequest):
    """Submit quiz answers and get results."""
    conn = get_connection()
    try:
        quiz = conn.execute("SELECT * FROM quizzes WHERE id=?", (quiz_id,)).fetchone()
        if not quiz:
            raise HTTPException(status_code=404, detail="Quiz not found")

        results = []
        correct_count = 0

        for ans in request.answers:
            q_id = ans.get("question_id", "")
            user_answer = ans.get("user_answer", "")

            question = conn.execute(
                "SELECT * FROM quiz_questions WHERE id=?", (q_id,)
            ).fetchone()
            if not question:
                continue

            is_correct = user_answer.strip().lower() == question["correct_answer"].strip().lower()
            if is_correct:
                correct_count += 1

            results.append(QuizResultItem(
                question_id=q_id,
                question_text=question["question_text"],
                user_answer=user_answer,
                correct_answer=question["correct_answer"],
                is_correct=is_correct,
                explanation=question["explanation"],
            ))

            # Save answer record
            conn.execute(
                "INSERT INTO quiz_answers (id, quiz_id, question_id, user_answer, is_correct) VALUES (?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), quiz_id, q_id, user_answer, 1 if is_correct else 0),
            )

            # Save wrong answer if incorrect
            if not is_correct:
                conn.execute(
                    """INSERT INTO wrong_answers
                       (id, question_id, quiz_id, question_text, question_type, options,
                        correct_answer, explanation, user_answer)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        str(uuid.uuid4()), q_id, quiz_id,
                        question["question_text"], question["question_type"],
                        question["options"], question["correct_answer"],
                        question["explanation"], user_answer,
                    ),
                )

            # Update knowledge point mastery
            # Find related knowledge points by doc
            try:
                source_chunk = question["source_chunk_id"]
            except (IndexError, KeyError):
                source_chunk = None

            if source_chunk:
                doc_row = conn.execute(
                    """SELECT d.id, d.filename FROM documents d
                       JOIN chunks c ON c.doc_id = d.id
                       WHERE c.id = ?""",
                    (source_chunk,),
                ).fetchone()

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
    finally:
        conn.close()


# -- Wrong Answers -------------------------------------------------

@router.get("/wrong-answers", response_model=list[WrongAnswerResponse])
async def list_wrong_answers():
    """List all wrong answers for review."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM wrong_answers ORDER BY mastery_level ASC, created_at DESC"
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
    finally:
        conn.close()


@router.post("/wrong-answers/{answer_id}/review")
async def review_wrong_answer(answer_id: str, is_correct: bool):
    """Mark a wrong answer as reviewed (correct or still wrong)."""
    conn = get_connection()
    try:
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
    finally:
        conn.close()


# -- Anki Export ---------------------------------------------------

@router.get("/anki/export")
async def export_to_anki(tag: str | None = None, doc_id: str | None = None):
    """Export quiz questions as Anki-compatible CSV."""
    conn = get_connection()
    try:
        # Gather questions from quizzes (optionally filtered)
        if doc_id:
            questions = conn.execute(
                """SELECT qq.*, q.topic FROM quiz_questions qq
                   JOIN quizzes q ON q.id = qq.quiz_id
                   WHERE q.doc_ids LIKE ?""",
                (f'%{doc_id}%',),
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
        writer = csv.writer(output, delimiter='\t')
        # Anki basic format: Front, Back, Tags
        for q in questions:
            front = q["question_text"]
            if q["question_type"] == "choice" and q["options"]:
                options = json.loads(q["options"])
                front += "\n" + "\n".join(f"{chr(65+i)}. {opt}" for i, opt in enumerate(options))

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
    finally:
        conn.close()


# -- Dashboard -----------------------------------------------------

@router.get("/dashboard")
async def get_dashboard():
    """Get learning dashboard statistics."""
    conn = get_connection()
    try:
        total_docs = conn.execute("SELECT COUNT(*) as c FROM documents WHERE status='ready'").fetchone()["c"]
        total_chunks = conn.execute("SELECT COUNT(*) as c FROM chunks").fetchone()["c"]
        total_questions = conn.execute("SELECT COUNT(*) as c FROM chat_messages WHERE role='user'").fetchone()["c"]
        total_quizzes = conn.execute("SELECT COUNT(*) as c FROM quizzes").fetchone()["c"]

        # Tag statistics
        tag_stats = []
        tag_rows = conn.execute(
            """SELECT t.name, COUNT(dt.doc_id) as doc_count
               FROM tags t
               LEFT JOIN document_tags dt ON dt.tag_id = t.id
               GROUP BY t.id"""
        ).fetchall()
        for t in tag_rows:
            # Count questions asked about docs with this tag
            q_count = conn.execute(
                """SELECT COUNT(*) as c FROM chat_messages cm
                   JOIN chat_sessions cs ON cs.id = cm.session_id
                   JOIN document_tags dt ON dt.tag_id IN (
                       SELECT id FROM tags WHERE name = ?
                   )
                   WHERE cm.role = 'user'""",
                (t["name"],),
            ).fetchone()["c"]
            tag_stats.append({
                "tag": t["name"],
                "doc_count": t["doc_count"],
                "question_count": q_count,
            })

        # Weak points (knowledge points with low mastery)
        weak_points = []
        kp_rows = conn.execute(
            "SELECT name, mastery_score FROM knowledge_points ORDER BY mastery_score ASC LIMIT 10"
        ).fetchall()
        for kp in kp_rows:
            weak_points.append({
                "concept": kp["name"],
                "mastery_score": kp["mastery_score"],
            })

        # Recent activity (last 7 days)
        recent_activity = []
        for i in range(7):
            date_offset = i
            row = conn.execute(
                """SELECT
                   COUNT(CASE WHEN role='user' THEN 1 END) as questions,
                   COUNT(DISTINCT CASE WHEN role='user' THEN session_id END) as sessions
                   FROM chat_messages
                   WHERE DATE(created_at) = DATE('now', ?)""",
                (f'-{date_offset} days',),
            ).fetchone()
            recent_activity.append({
                "date": f"-{date_offset}d",
                "questions_count": row["questions"],
                "sessions": row["sessions"],
            })

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
    finally:
        conn.close()
