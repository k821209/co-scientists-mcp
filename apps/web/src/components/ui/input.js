import { jsx as _jsx } from "react/jsx-runtime";
import { forwardRef } from "react";
import { cn } from "@/lib/utils";
export const Input = forwardRef(({ className, type, ...props }, ref) => (_jsx("input", { ref: ref, type: type, className: cn("flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm", "ring-offset-background placeholder:text-muted-foreground", "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring", "disabled:cursor-not-allowed disabled:opacity-50", className), ...props })));
Input.displayName = "Input";
