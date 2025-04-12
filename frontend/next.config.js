/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  distDir: 'build',
  // Required for static export to work properly
  images: {
    unoptimized: true
  },
  // Ensure trailing slashes for better compatibility with Flask routing
  trailingSlash: true,
};

export default nextConfig;
