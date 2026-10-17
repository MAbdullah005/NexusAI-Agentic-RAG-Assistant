/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Allow proxying backend API during dev if desired
  async rewrites() {
    return [
      {
        source: "/api/backend/:path*",
        destination: "http://127.0.0.1:8000/:path*",
      },
    ];
  },
};

export default nextConfig;

