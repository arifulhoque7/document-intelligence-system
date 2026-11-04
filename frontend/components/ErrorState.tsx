import { errorMessage } from "@/lib/api";
import { Alert } from "./Alert";
import { Button } from "./ui/button";

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <Alert tone="error" title="Could not load data" action={onRetry && <Button size="compact" variant="outline" onClick={onRetry}>Try again</Button>}>
      {errorMessage(error)}
    </Alert>
  );
}
