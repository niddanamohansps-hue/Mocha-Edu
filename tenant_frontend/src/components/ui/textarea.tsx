import * as React from "react"

import { cn } from "@/lib/utils"

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "border-input placeholder:text-muted-foreground aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive dark:bg-input/30 flex min-h-[100px] w-full rounded-lg border bg-transparent px-3.5 py-2.5 text-sm shadow-2xs transition-all duration-150 ease-out outline-none hover:border-slate-300 dark:hover:border-slate-700 focus-visible:border-sky-500 focus-visible:ring-2 focus-visible:ring-sky-500/20 dark:focus-visible:ring-sky-400/25 disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      {...props}
    />
  )
}

export { Textarea }
