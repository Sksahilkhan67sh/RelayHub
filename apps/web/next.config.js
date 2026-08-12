/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Standalone output produces a self-contained server bundle (minimal
  // node_modules trace) under `.next/standalone` -- this is what the
  // production Dockerfile (Phase E, infra/docker/frontend.Dockerfile) copies
  // into the final image instead of shipping the full node_modules tree.
  output: "standalone",
};

module.exports = nextConfig;
