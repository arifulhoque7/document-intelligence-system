import { ScanText } from "lucide-react";
import { Suspense } from "react";
import { LoginForm } from "./LoginForm";

export const metadata = { title: "Log in" };

export default function LoginPage() {
  return (
    <main className="flex min-h-svh flex-col items-center justify-center gap-6 bg-background p-6 md:p-10">
      <div className="w-full max-w-[400px]">
        <div className="flex flex-col gap-8">
          <div className="flex flex-col items-center gap-3">
            <div className="flex flex-col items-center gap-2 font-medium">
              <div className="flex size-11 items-center justify-center rounded-md bg-primary text-primary-foreground">
                <ScanText className="size-6" aria-hidden />
              </div>
              <span className="text-base font-semibold text-foreground">DocIntel</span>
            </div>
            <div className="space-y-2 text-center">
              <h1 className="text-xl font-semibold text-foreground">Log in to your account</h1>
              <p className="text-sm text-muted-foreground">Enter your email and password below to log in</p>
            </div>
          </div>
          <Suspense>
            <LoginForm />
          </Suspense>
        </div>
      </div>
    </main>
  );
}
