export default function HexagonIcon({ className = "brand-hexagon-icon", size = 40, style = {} }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="44 34 132 152"
      width={size}
      height={size}
      className={className}
      style={{
        color: "currentColor",
        display: "inline-block",
        verticalAlign: "middle",
        flexShrink: 0,
        ...style,
      }}
    >
      <title>PaperMind Hexagon Icon</title>
      {/* Outer Ring */}
      <polygon
        fill="none"
        stroke="currentColor"
        strokeWidth="7"
        strokeLinejoin="round"
        points="110,38 172.4,74 172.4,146 110,182 47.6,146 47.6,74"
      />
      {/* Inner Solid Hexagon Core */}
      <polygon
        fill="currentColor"
        points="110,64 149.8,87 149.8,133 110,156 70.2,133 70.2,87"
      />
    </svg>
  );
}
