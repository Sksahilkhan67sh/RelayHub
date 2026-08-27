import { ImageResponse } from "next/og";

// Applies to every marketing page that doesn't define its own
// opengraph-image/twitter-image (Next.js falls back to this file for both
// og:image and twitter:image). Generated at request time from real brand
// tokens (see tailwind.config.ts) -- not a static/fabricated asset.

export const runtime = "edge";
export const alt = "RelayHub — Webhook delivery infrastructure that doesn't drop events";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "72px",
          background: "#14171A",
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
          <div
            style={{
              width: "40px",
              height: "40px",
              borderRadius: "10px",
              background: "#C17F2B",
              display: "flex",
            }}
          />
          <div style={{ fontSize: "30px", fontWeight: 600, color: "#F6F7F8" }}>RelayHub</div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
          <div
            style={{
              fontSize: "54px",
              fontWeight: 600,
              lineHeight: 1.15,
              color: "#F6F7F8",
              maxWidth: "980px",
            }}
          >
            Every event you send, delivered — or you&apos;ll know exactly why not.
          </div>
          <div style={{ fontSize: "26px", color: "#AFB4BB", maxWidth: "820px" }}>
            Signed deliveries, automatic retries, a real dead-letter queue, and full delivery logs.
          </div>
        </div>
      </div>
    ),
    { ...size }
  );
}
