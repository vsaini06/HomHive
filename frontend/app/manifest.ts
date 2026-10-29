import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "HomHive",
    short_name: "HomHive",
    description: "Household intelligence that turns evidence into action.",
    start_url: "/",
    icons: [{src: "/branding/homhive-192.png", sizes: "192x192", type: "image/png"}, {src: "/branding/homhive-512.png", sizes: "512x512", type: "image/png"}],
    display: "standalone",
    background_color: "#f7f7f2",
    theme_color: "#1d2b24",
  };
}
