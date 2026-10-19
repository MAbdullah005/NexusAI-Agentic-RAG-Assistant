import * as React from "react";
import { cn } from "../../lib/utils";

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "destructive" | "outline" | "secondary" | "ghost" | "link";
  size?: "default" | "sm" | "lg" | "icon";
  isLoading?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = "default",
      size = "default",
      isLoading = false,
      children,
      disabled,
      ...props
    },
    ref
  ) => {
    const baseStyles =
      "inline-flex items-center justify-center whitespace-nowrap rounded-lg text-sm font-medium transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-pink-400/50 disabled:pointer-events-none disabled:opacity-50 select-none active:scale-[0.98]";

    const variantStyles = {
      default:
        "bg-gradient-to-r from-pink-500 to-rose-500 hover:from-pink-600 hover:to-rose-600 text-white shadow-sm shadow-pink-500/25 hover:shadow-pink-500/35",
      destructive:
        "bg-rose-600 text-white hover:bg-rose-500 shadow-sm shadow-rose-950/50",
      outline:
        "border border-pink-100 dark:border-zinc-800 bg-white dark:bg-zinc-900/60 text-slate-700 dark:text-zinc-200 hover:bg-pink-50/60 dark:hover:bg-zinc-800/80 hover:text-slate-900 dark:hover:text-white hover:border-pink-200 dark:hover:border-zinc-700",
      secondary:
        "bg-pink-50 dark:bg-zinc-800 text-pink-700 dark:text-zinc-100 hover:bg-pink-100 dark:hover:bg-zinc-700/80 hover:text-pink-800 dark:hover:text-white border border-pink-100 dark:border-zinc-700/50",
      ghost:
        "text-slate-600 dark:text-zinc-400 hover:text-pink-600 dark:hover:text-zinc-100 hover:bg-pink-50/60 dark:hover:bg-zinc-800/60",
      link:
        "text-pink-600 dark:text-pink-400 underline-offset-4 hover:underline hover:text-pink-700 dark:hover:text-pink-300",
    };

    const sizeStyles = {
      default: "h-9 px-4 py-2",
      sm: "h-8 rounded-md px-3 text-xs",
      lg: "h-10 rounded-lg px-6 text-base",
      icon: "h-8 w-8 p-0 rounded-md",
    };

    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        className={cn(
          baseStyles,
          variantStyles[variant],
          sizeStyles[size],
          className
        )}
        {...props}
      >
        {isLoading && (
          <svg
            className="mr-2 h-4 w-4 animate-spin text-current"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
        )}
        {children}
      </button>
    );
  }
);
Button.displayName = "Button";

export { Button };

