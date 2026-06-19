/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Self-contained server build for Docker (emits .next/standalone)
  output: 'standalone',
  async rewrites() {
    // Server-side proxy target. In Docker this is the compose service name
    // (http://backend:8000); locally it falls back to localhost.
    const backendUrl = process.env.BACKEND_INTERNAL_URL || 'http://localhost:8000';
    return [
      {
        source: '/api/backend/:path*',
        destination: `${backendUrl}/api/v1/:path*`,
      },
    ];
  },
};
export default nextConfig;
