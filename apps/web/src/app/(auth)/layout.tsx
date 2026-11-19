import Link from "next/link";
import { ResponsibleGamblingLine } from "@/components/ui/helpline";
import { Logo } from "@/components/ui/logo";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col">
      <header className="px-4 py-5 sm:px-6">
        <Link href="/" aria-label="OddVex home">
          <Logo />
        </Link>
      </header>
      <main id="main" className="mx-auto w-full max-w-md flex-1 px-4 pb-16 pt-6 sm:pt-12">
        {children}
      </main>
      <footer className="px-4 py-6 text-center">
        <ResponsibleGamblingLine />
      </footer>
    </div>
  );
}
