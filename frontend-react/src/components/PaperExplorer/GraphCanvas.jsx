import { useEffect, useRef, useCallback } from "react";
import * as d3 from "d3";

// Colour palette by first-letter bucket (decorative, not semantic)
const NODE_COLORS = [
  "#38bdf8", "#34d399", "#a78bfa", "#fb923c",
  "#f472b6", "#facc15", "#60a5fa", "#4ade80",
];

export default function GraphCanvas({ nodes, selectedNode, onNodeClick }) {
  const svgRef = useRef(null);
  const simRef = useRef(null);

  const handleClick = useCallback(
    (event, d) => {
      event.stopPropagation();
      onNodeClick(d);
    },
    [onNodeClick]
  );

  useEffect(() => {
    if (!nodes || nodes.length === 0) return;

    const el = svgRef.current;
    const W = el.clientWidth || 900;
    const H = el.clientHeight || 560;

    // Clear previous
    d3.select(el).selectAll("*").remove();

    const svg = d3.select(el)
      .attr("width", W)
      .attr("height", H);

    // Defs: radial gradient glow per colour
    const defs = svg.append("defs");
    NODE_COLORS.forEach((color, index) => {
      const grad = defs.append("radialGradient")
        .attr("id", `ng-${index}`)
        .attr("cx", "40%").attr("cy", "35%");
      grad.append("stop").attr("offset", "0%").attr("stop-color", d3.color(color).brighter(0.8));
      grad.append("stop").attr("offset", "100%").attr("stop-color", color);
    });

    // Drop-shadow filter
    const filter = defs.append("filter").attr("id", "node-shadow");
    filter.append("feDropShadow")
      .attr("dx", 0).attr("dy", 2)
      .attr("stdDeviation", 6)
      .attr("flood-opacity", 0.4);

    // Background click → deselect
    svg.append("rect")
      .attr("width", W).attr("height", H)
      .attr("fill", "transparent")
      .on("click", () => onNodeClick(null));

    const data = nodes.map((n) => ({
      ...n,
      x: W / 2 + (Math.random() - 0.5) * 300,
      y: H / 2 + (Math.random() - 0.5) * 200,
      colorIdx: n.label.charCodeAt(0) % NODE_COLORS.length,
    }));

    // D3 force simulation — nodes only (no links)
    const sim = d3.forceSimulation(data)
      .force("charge", d3.forceManyBody().strength(-220))
      .force("center", d3.forceCenter(W / 2, H / 2))
      .force("collision", d3.forceCollide().radius(52))
      .force("x", d3.forceX(W / 2).strength(0.04))
      .force("y", d3.forceY(H / 2).strength(0.04));

    simRef.current = sim;

    const nodeGroup = svg.selectAll("g.node")
      .data(data)
      .join("g")
      .attr("class", "node")
      .style("cursor", "pointer")
      .call(
        d3.drag()
          .on("start", (event, d) => {
            if (!event.active) sim.alphaTarget(0.3).restart();
            d.fx = d.x; d.fy = d.y;
          })
          .on("drag", (event, d) => { d.fx = event.x; d.fy = event.y; })
          .on("end", (event, d) => {
            if (!event.active) sim.alphaTarget(0);
            d.fx = null; d.fy = null;
          })
      )
      .on("click", handleClick);

    // Outer glow ring (shown when selected)
    nodeGroup.append("circle")
      .attr("class", "node-ring")
      .attr("r", 36)
      .attr("fill", "none")
      .attr("stroke", (d) => NODE_COLORS[d.colorIdx])
      .attr("stroke-width", 2)
      .attr("opacity", 0)
      .attr("filter", "url(#node-shadow)");

    // Main circle
    nodeGroup.append("circle")
      .attr("class", "node-circle")
      .attr("r", 28)
      .attr("fill", (d) => `url(#ng-${d.colorIdx})`)
      .attr("filter", "url(#node-shadow)")
      .attr("stroke", (d) => NODE_COLORS[d.colorIdx])
      .attr("stroke-width", 1.5);

    // Label below circle
    nodeGroup.append("text")
      .attr("class", "node-label")
      .attr("dy", 44)
      .attr("text-anchor", "middle")
      .attr("font-size", "11px")
      .attr("font-family", "Inter, sans-serif")
      .attr("font-weight", "600")
      .attr("fill", "#f8fafc")
      .attr("paint-order", "stroke")
      .attr("stroke", "rgba(9,13,22,0.8)")
      .attr("stroke-width", 3)
      .text((d) => d.label.length > 16 ? d.label.slice(0, 14) + "…" : d.label);

    // Source count badge
    nodeGroup.append("text")
      .attr("class", "node-badge")
      .attr("dy", "0.35em")
      .attr("text-anchor", "middle")
      .attr("font-size", "10px")
      .attr("font-family", "Inter, sans-serif")
      .attr("font-weight", "700")
      .attr("fill", "rgba(255,255,255,0.9)")
      .text((d) => d.sources?.length || "");

    // Tick
    sim.on("tick", () => {
      nodeGroup.attr("transform", (d) => {
        d.x = Math.max(50, Math.min(W - 50, d.x));
        d.y = Math.max(50, Math.min(H - 50, d.y));
        return `translate(${d.x},${d.y})`;
      });
    });

    return () => sim.stop();
  }, [nodes, handleClick, onNodeClick]);

  // Highlight selected node reactively
  useEffect(() => {
    if (!svgRef.current) return;
    d3.select(svgRef.current).selectAll("g.node").each(function (d) {
      const isSelected = selectedNode && d.id === selectedNode.id;
      d3.select(this).select(".node-ring").attr("opacity", isSelected ? 1 : 0);
      d3.select(this).select(".node-circle")
        .attr("stroke-width", isSelected ? 3 : 1.5)
        .attr("r", isSelected ? 32 : 28);
    });
  }, [selectedNode]);

  return (
    <svg
      ref={svgRef}
      className="graph-svg"
      style={{ width: "100%", height: "100%" }}
    />
  );
}
