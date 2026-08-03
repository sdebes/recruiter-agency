/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // We can add rewriting rules here if we want to proxy calls from /api to localhost:8000.
  // E.g.,
  // async rewrites() {
  //   return [
  //     {
  //       source: '/api/:path*',
  //       destination: 'http://127.0.0.1:8000/api/:path*',
  //     },
  //   ];
  // },
};

module.exports = nextConfig;
