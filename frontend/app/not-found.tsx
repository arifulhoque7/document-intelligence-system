import { FileQuestion } from "lucide-react";
import Link from "next/link";
import { EmptyState } from "@/components/EmptyState";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <main className="mx-auto max-w-md py-24">
      <EmptyState
        icon={FileQuestion}
        title="Page not found"
        description="The page you asked for does not exist."
        action={
          <Button asChild variant="outline">
            <Link href="/">Go to dashboard</Link>
          </Button>
        }
      />
    </main>
  );
}
