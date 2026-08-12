import { ImageResponse } from "next/og";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          padding: 80,
          background: "#14171A",
          color: "#F6F7F8",
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div style={{ width: 48, height: 48, borderRadius: 12, background: "#14171A", border: "2px solid #3D444C", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
              <div style={{ width: 10, height: 10, borderRadius: 999, background: "#C17F2B" }} />
              <div style={{ width: 14, height: 2, background: "#8A9099" }} />
              <div style={{ width: 10, height: 10, borderRadius: 999, background: "#1D8A5E" }} />
            </div>
          </div>
          <div style={{ display: "flex", fontSize: 34, fontWeight: 600 }}>RelayHub</div>
        </div>
        <div style={{ display: "flex", marginTop: 48, fontSize: 54, fontWeight: 600, lineHeight: 1.15, maxWidth: 950 }}>
          Every event you send, delivered.
        </div>
        <div style={{ display: "flex", marginTop: 20, fontSize: 26, color: "#8A9099", maxWidth: 850 }}>
          Signed deliveries, automatic retries, and a real dead-letter queue.
        </div>
      </div>
    ),
    { ...size }
  );
}
