export default function SiteTrust() {
  return (
    <section className="border-y border-white/10 bg-black py-20 md:py-24">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <p className="mx-auto max-w-2xl text-center text-base leading-relaxed text-zinc-400 md:text-lg">
          Trusted by professionals who need reliable truth verification at scale.
        </p>
        <div className="mx-auto mt-14 grid max-w-5xl grid-cols-2 items-center gap-x-10 gap-y-10 sm:grid-cols-3 md:grid-cols-6">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className="mx-auto flex h-9 w-full max-w-[100px] items-center justify-center rounded-sm border border-white/10 bg-white/[0.02]"
            >
              <span className="h-3 w-14 rounded-sm bg-white/20" />
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
