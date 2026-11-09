import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "URBIX",
    short_name: "URBIX",
    description: "Understand cities. Predict what comes next.",
    start_url: "/m",
    scope: "/",
    display: "standalone",
    background_color: "#07111c",
    theme_color: "#07111c",
    icons: [
      { src: "/icon", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/apple-icon", sizes: "180x180", type: "image/png" },
    ],
  };
}
