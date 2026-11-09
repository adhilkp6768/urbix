/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  eslint: { ignoreDuringBuilds: true },
  allowedDevOrigins: ["*.trycloudflare.com"],
};

module.exports = nextConfig;
