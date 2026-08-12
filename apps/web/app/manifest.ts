import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "RelayHub",
    short_name: "RelayHub",
    description: "Webhook and event delivery infrastructure",
    start_url: "/",
    display: "standalone",
    background_color: "#14171A",
    theme_color: "#14171A",
    icons: [
      { src: "/icon", sizes: "32x32", type: "image/png" },
      { src: "/apple-icon", sizes: "180x180", type: "image/png" },
    ],
  };
}
