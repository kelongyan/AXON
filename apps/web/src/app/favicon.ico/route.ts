const icon = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="12" fill="#0f766e"/>
  <path d="M18 41L31 15h6L24 41h-6zm16 8l13-26h6L40 49h-6z" fill="#ffffff"/>
</svg>`;


export function GET(): Response {
  return new Response(icon, {
    status: 200,
    headers: {
      "content-type": "image/svg+xml",
      "cache-control": "public, max-age=86400",
    },
  });
}

