import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-black">
      <div className="text-center">
        <h1 className="mb-4 text-4xl font-bold text-white">404</h1>
        <p className="mb-4 text-xl text-zinc-400">Oops! Page not found</p>
        <Link href="/" className="text-tl-body underline underline-offset-2 transition-colors duration-200 hover:text-tl-heading">
          Return to Home
        </Link>
      </div>
    </div>
  );
}
