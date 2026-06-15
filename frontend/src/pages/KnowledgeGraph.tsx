import { useState, useEffect, useRef, useCallback } from 'react';
import * as d3 from 'd3';
import { knowledgeGraphApi } from '../api';
import { useTranslation } from 'react-i18next';

interface GraphNode {
  id: string;
  name: string;
  category: string;
  description: string;
  doc_count: number;
  x?: number;
  y?: number;
  fx?: number | null;
  fy?: number | null;
}

interface GraphEdge {
  source: string | GraphNode;
  target: string | GraphNode;
  relation_type: string;
  strength: number;
}

interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

interface RelatedConcept {
  name: string;
  category: string;
  description: string;
  relation_type: string;
  strength: number;
  direction: string;
}

const CATEGORY_COLORS: Record<string, string> = {
  技术: '#3b82f6',
  人物: '#f59e0b',
  组织: '#10b981',
  概念: '#8b5cf6',
  方法: '#ef4444',
  工具: '#06b6d4',
  领域: '#ec4899',
  理论: '#f97316',
  默认: '#6b7280',
};

export default function KnowledgeGraph() {
  const { t } = useTranslation();
  const svgRef = useRef<SVGSVGElement>(null);
  const [graphData, setGraphData] = useState<GraphData>({ nodes: [], edges: [] });
  const [loading, setLoading] = useState(false);
  const [building, setBuilding] = useState(false);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [relatedConcepts, setRelatedConcepts] = useState<RelatedConcept[]>([]);
  const [message, setMessage] = useState('');
  const [isEmpty, setIsEmpty] = useState(false);

  const loadGraph = useCallback(async () => {
    setLoading(true);
    try {
      const data = await knowledgeGraphApi.getGraph();
      setGraphData(data);
      if (data.nodes.length === 0) {
        setIsEmpty(true);
        setMessage('');
      }
    } catch (error) {
      console.error('Failed to load graph:', error);
      setMessage(t('knowledgeGraph.error_load'));
    } finally {
      setLoading(false);
    }
  }, [t]);

  const buildGraph = async () => {
    setBuilding(true);
    setMessage(t('knowledgeGraph.building'));
    try {
      const result = await knowledgeGraphApi.build();
      setMessage(
        t('knowledgeGraph.buildComplete', {
          docs: result.documents_processed,
          concepts: result.concepts_added,
          relations: result.relations_added,
        })
      );
      await loadGraph();
    } catch (error) {
      console.error('Failed to build graph:', error);
      setMessage(t('knowledgeGraph.error_build'));
    } finally {
      setBuilding(false);
    }
  };

  const handleNodeClick = useCallback(async (node: GraphNode) => {
    setSelectedNode(node);
    try {
      const result = await knowledgeGraphApi.getRelated(node.name, 5);
      setRelatedConcepts(result.related);
    } catch (error) {
      console.error('Failed to get related concepts:', error);
      setRelatedConcepts([]);
    }
  }, []);

  const renderGraph = useCallback(() => {
    if (!svgRef.current) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const width = svgRef.current.clientWidth;
    const height = svgRef.current.clientHeight;

    const g = svg.append('g');

    // Zoom behavior
    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform);
      });

    svg.call(zoom);

    // Create force simulation
    const simulation = d3
      .forceSimulation<GraphNode>(graphData.nodes)
      .force(
        'link',
        d3
          .forceLink<GraphNode, GraphEdge>(graphData.edges)
          .id((d) => d.id)
          .distance((d) => 150 / Math.sqrt(d.strength))
      )
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(30));

    // Draw edges
    const link = g
      .append('g')
      .selectAll<SVGLineElement, GraphEdge>('line')
      .data(graphData.edges)
      .join('line')
      .attr('stroke', '#94a3b8')
      .attr('stroke-opacity', 0.5)
      .attr('stroke-width', (d: GraphEdge) => Math.sqrt(d.strength) * 2);

    // Edge labels
    const linkLabel = g
      .append('g')
      .selectAll<SVGTextElement, GraphEdge>('text')
      .data(graphData.edges)
      .join('text')
      .attr('font-size', '10px')
      .attr('fill', '#64748b')
      .text((d: GraphEdge) => d.relation_type);

    // Draw nodes
    const node = g
      .append('g')
      .selectAll<SVGGElement, GraphNode>('g')
      .data(graphData.nodes)
      .join('g')
      .call(
        d3
          .drag<SVGGElement, GraphNode>()
          .on('start', dragstarted)
          .on('drag', dragged)
          .on('end', dragended)
      );

    // Node shadow
    node
      .append('circle')
      .attr('r', (d: GraphNode) => 10 + d.doc_count * 2)
      .attr('fill', 'rgba(0,0,0,0.05)')
      .attr('transform', 'translate(1,1)');

    node
      .append('circle')
      .attr('r', (d: GraphNode) => 8 + d.doc_count * 2)
      .attr('fill', (d: GraphNode) => CATEGORY_COLORS[d.category] || CATEGORY_COLORS['默认'])
      .attr('stroke', '#fff')
      .attr('stroke-width', 2.5)
      .style('cursor', 'pointer')
      .on('click', (event: MouseEvent, d: GraphNode) => {
        event.stopPropagation();
        handleNodeClick(d);
      })
      .append('title')
      .text(
        (d: GraphNode) =>
          `${d.name} (${d.category})\n${d.description}\n${t('knowledgeGraph.occurrences')} ${d.doc_count}`
      );

    node
      .append('text')
      .attr('dx', 14)
      .attr('dy', '.35em')
      .attr('font-size', '12px')
      .attr('fill', '#334155')
      .attr('font-weight', '500')
      .text((d: GraphNode) => d.name);

    // Update positions on tick
    simulation.on('tick', () => {
      link
        .attr('x1', (d: GraphEdge) => (d.source as GraphNode).x!)
        .attr('y1', (d: GraphEdge) => (d.source as GraphNode).y!)
        .attr('x2', (d: GraphEdge) => (d.target as GraphNode).x!)
        .attr('y2', (d: GraphEdge) => (d.target as GraphNode).y!);

      linkLabel
        .attr('x', (d: GraphEdge) => ((d.source as GraphNode).x! + (d.target as GraphNode).x!) / 2)
        .attr('y', (d: GraphEdge) => ((d.source as GraphNode).y! + (d.target as GraphNode).y!) / 2);

      node.attr('transform', (d: GraphNode) => `translate(${d.x},${d.y})`);
    });

    function dragstarted(event: d3.D3DragEvent<SVGGElement, GraphNode, GraphNode>, d: GraphNode) {
      if (!event.active) simulation.alphaTarget(0.3).restart();
      d.fx = d.x;
      d.fy = d.y;
    }

    function dragged(event: d3.D3DragEvent<SVGGElement, GraphNode, GraphNode>, d: GraphNode) {
      d.fx = event.x;
      d.fy = event.y;
    }

    function dragended(event: d3.D3DragEvent<SVGGElement, GraphNode, GraphNode>, d: GraphNode) {
      if (!event.active) simulation.alphaTarget(0);
      d.fx = null;
      d.fy = null;
    }
  }, [graphData, handleNodeClick, t]);

  useEffect(() => {
    loadGraph();
  }, [loadGraph]);

  useEffect(() => {
    if (graphData.nodes.length > 0 && svgRef.current) {
      setIsEmpty(false);
      renderGraph();
    } else {
      setIsEmpty(true);
    }
  }, [graphData, renderGraph]);

  return (
    <div className="spell-page h-full flex">
      {/* Main graph area */}
      <div className="flex-1 relative graph-grid-bg">
        {/* Toolbar */}
        <div className="absolute top-4 left-4 z-10 flex gap-2">
          <button
            onClick={buildGraph}
            disabled={building}
            className="spell-button px-4 py-2.5 bg-gradient-to-r from-blue-600 to-indigo-500 text-white rounded-lg hover:from-blue-700 hover:to-indigo-600 disabled:from-gray-400 disabled:to-gray-400 transition-all duration-200 shadow-sm hover:shadow-md text-sm font-medium"
          >
            {building ? t('common.building') : t('knowledgeGraph.buildGraph')}
          </button>
          <button
            onClick={loadGraph}
            disabled={loading}
            className="px-4 py-2.5 bg-white text-gray-700 rounded-lg hover:bg-gray-50 disabled:bg-gray-100 transition-all duration-200 shadow-sm border border-gray-200 text-sm font-medium"
          >
            {loading ? t('common.loading') : t('common.refresh')}
          </button>
        </div>

        {message && (
          <div className="absolute top-4 right-4 z-10 bg-white p-3 rounded-xl shadow-lg border border-gray-100 max-w-md">
            <p className="text-sm text-gray-700">{message}</p>
          </div>
        )}

        {/* Empty State */}
        {isEmpty && !loading && (
          <div className="absolute inset-0 flex items-center justify-center z-0">
            <div className="text-center max-w-md">
              <div className="w-20 h-20 mx-auto mb-6 bg-gradient-to-br from-indigo-100 to-purple-100 rounded-2xl flex items-center justify-center shadow-sm">
                <span className="text-4xl">🔗</span>
              </div>
              <p className="text-gray-700 font-semibold text-lg mb-2">
                {t('knowledgeGraph.notBuilt')}
              </p>
              <p className="text-sm text-gray-400 mb-6 leading-relaxed">
                {t('knowledgeGraph.notBuiltHint')}
              </p>
              <div className="bg-white rounded-xl border border-gray-200 p-5 text-left shadow-sm">
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
                  {t('knowledgeGraph.steps')}
                </p>
                <div className="space-y-3">
                  <div className="flex items-start gap-3">
                    <div className="w-7 h-7 rounded-full bg-blue-50 flex items-center justify-center flex-shrink-0">
                      <span className="text-xs font-bold text-blue-600">1</span>
                    </div>
                    <div>
                      <p className="text-sm text-gray-700 font-medium">
                        {t('knowledgeGraph.step1_title')}
                      </p>
                      <p className="text-xs text-gray-400">{t('knowledgeGraph.step1_desc')}</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <div className="w-7 h-7 rounded-full bg-blue-50 flex items-center justify-center flex-shrink-0">
                      <span className="text-xs font-bold text-blue-600">2</span>
                    </div>
                    <div>
                      <p className="text-sm text-gray-700 font-medium">
                        {t('knowledgeGraph.step2_title')}
                      </p>
                      <p className="text-xs text-gray-400">{t('knowledgeGraph.step2_desc')}</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <div className="w-7 h-7 rounded-full bg-blue-50 flex items-center justify-center flex-shrink-0">
                      <span className="text-xs font-bold text-blue-600">3</span>
                    </div>
                    <div>
                      <p className="text-sm text-gray-700 font-medium">
                        {t('knowledgeGraph.step3_title')}
                      </p>
                      <p className="text-xs text-gray-400">{t('knowledgeGraph.step3_desc')}</p>
                    </div>
                  </div>
                </div>
              </div>
              <button
                onClick={buildGraph}
                disabled={building}
                className="mt-6 px-6 py-3 bg-gradient-to-r from-blue-600 to-blue-500 text-white rounded-lg hover:from-blue-700 hover:to-blue-600 disabled:opacity-50 transition-all duration-200 shadow-sm hover:shadow-md text-sm font-medium"
              >
                {building ? t('common.building') : t('knowledgeGraph.buildNow')}
              </button>
            </div>
          </div>
        )}

        {/* SVG with grid background */}
        <svg ref={svgRef} className="w-full h-full graph-grid-bg" />

        {/* Legend */}
        {graphData.nodes.length > 0 && (
          <div className="absolute bottom-4 left-4 bg-white/95 backdrop-blur-sm p-4 rounded-xl shadow-lg border border-gray-100">
            <p className="text-xs font-semibold mb-2 text-gray-600">
              {t('knowledgeGraph.categoryLegend')}
            </p>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
              {Object.entries(CATEGORY_COLORS).map(([cat, color]) => (
                <div key={cat} className="flex items-center gap-1.5">
                  <div
                    className="w-3 h-3 rounded-full shadow-sm"
                    style={{ backgroundColor: color }}
                  />
                  <span className="text-gray-600">
                    {t(`knowledgeGraph.categories.${cat}`, cat)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Detail panel */}
      {selectedNode && (
        <div className="w-80 bg-white border-l border-gray-200 p-5 overflow-y-auto shadow-lg">
          <div className="flex justify-between items-start mb-4">
            <h3 className="text-lg font-bold text-gray-800">{selectedNode.name}</h3>
            <button
              onClick={() => setSelectedNode(null)}
              className="w-7 h-7 rounded-lg bg-gray-100 flex items-center justify-center text-gray-400 hover:text-gray-600 hover:bg-gray-200 transition-colors"
            >
              ✕
            </button>
          </div>

          <div className="mb-4">
            <span
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-full text-white font-medium shadow-sm"
              style={{
                backgroundColor: CATEGORY_COLORS[selectedNode.category] || CATEGORY_COLORS['默认'],
              }}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-white/50"></span>
              {selectedNode.category}
            </span>
          </div>

          <div className="mb-4 bg-gray-50 rounded-lg p-3 border border-gray-100">
            <p className="text-sm text-gray-600 leading-relaxed">{selectedNode.description}</p>
          </div>

          <div className="mb-5 flex items-center gap-2">
            <span className="text-sm text-gray-500">{t('knowledgeGraph.occurrences')}</span>
            <span className="font-bold text-gray-800 text-lg">{selectedNode.doc_count}</span>
          </div>

          {relatedConcepts.length > 0 && (
            <div>
              <h4 className="font-semibold text-gray-700 mb-3 flex items-center gap-2">
                <span className="w-1 h-4 bg-blue-500 rounded-full"></span>
                {t('knowledgeGraph.relatedConcepts')}
              </h4>
              <div className="space-y-2">
                {relatedConcepts.map((rel, idx) => (
                  <div
                    key={idx}
                    className="p-3 bg-gray-50 rounded-lg border border-gray-100 hover:bg-gray-100 transition-colors"
                  >
                    <div className="flex justify-between items-center mb-1">
                      <span className="font-medium text-sm text-gray-800">{rel.name}</span>
                      <span className="text-xs px-2 py-0.5 bg-white rounded-full text-gray-500 border border-gray-200">
                        {rel.relation_type}
                      </span>
                    </div>
                    <p className="text-xs text-gray-500 leading-relaxed">{rel.description}</p>
                    {/* Strength indicator */}
                    <div className="mt-2 flex items-center gap-2">
                      <div className="flex-1 h-1 bg-gray-200 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-blue-400 rounded-full"
                          style={{ width: `${rel.strength * 100}%` }}
                        />
                      </div>
                      <span className="text-xs text-gray-400">
                        {Math.round(rel.strength * 100)}%
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
