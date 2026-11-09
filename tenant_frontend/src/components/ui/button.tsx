import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-all disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4 shrink-0 [&_svg]:shrink-0 outline-none focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive cursor-pointer touch-manipulation select-none active:scale-[0.98]",
  {
    variants: {
      variant: {
        default: "bg-sky-600 hover:bg-teal-600 shadow-lg shadow-sky-500/25 hover:shadow-xl hover:shadow-teal-500/30 hover:scale-[1.03] active:scale-100 transition-all text-base font-bold text-white duration-300 ease-out",
        destructive:
          "bg-destructive text-white hover:bg-destructive/90 hover:scale-[1.03] active:scale-100 transition-all duration-300 ease-out focus-visible:ring-destructive/20 dark:focus-visible:ring-destructive/40 dark:bg-destructive/60",
        outline:
          "border bg-background shadow-lg hover:bg-accent hover:text-accent-foreground hover:scale-[1.03] active:scale-100 transition-all duration-300 ease-out dark:bg-input/30 dark:border-input dark:hover:bg-input/50 border-[#1A82C4] text-[#1A82C4]",
        secondary:
          "bg-secondary text-secondary-foreground hover:bg-secondary/80 hover:scale-[1.03] active:scale-100 transition-all duration-300 ease-out",
        ghost:
          "hover:bg-accent hover:text-accent-foreground dark:hover:bg-accent/50 transition-colors duration-200",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "min-h-[42px] sm:min-h-0 h-10 sm:h-9 px-4 py-2 has-[>svg]:px-3",
        sm: "min-h-[38px] sm:min-h-0 h-9 sm:h-8 rounded-md gap-1.5 px-3.5 sm:px-3 has-[>svg]:px-2.5 text-xs sm:text-xs",
        lg: "min-h-[46px] sm:min-h-0 h-11 sm:h-10 rounded-md px-6 has-[>svg]:px-4",
        xl: "min-h-[50px] sm:min-h-0 h-12 rounded-md px-8 has-[>svg]:px-4",
        xxl: "min-h-[58px] sm:min-h-0 h-14 rounded-md px-10 has-[>svg]:px-4",
        icon: "size-10 sm:size-9",
        "icon-sm": "size-9 sm:size-8",
        "icon-lg": "size-11 sm:size-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

function Button({
  className,
  variant = "default",
  size = "default",
  asChild = false,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
  }) {
  const Comp = asChild ? Slot : "button"

  return (
    <Comp
      data-slot="button"
      data-variant={variant}
      data-size={size}
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
