import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

/** An image that opens a full-screen lightbox when clicked.
 *  Close via the image, the backdrop, the X button, or Escape. */
export function ZoomableImage({ src, alt, className }: {
  src: string;
  alt?: string;
  className?: string;
}) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";  // lock scroll behind the overlay
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [open]);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label={alt ? `Enlarge: ${alt}` : "Enlarge image"}
        className="block cursor-zoom-in"
      >
        <img src={src} alt={alt} className={className} />
      </button>

      {open && createPortal(
        <div
          role="dialog"
          aria-modal="true"
          onClick={() => setOpen(false)}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"
        >
          <button
            type="button"
            aria-label="Close"
            onClick={() => setOpen(false)}
            className="absolute right-3 top-3 rounded-md bg-white/10 p-2 text-white transition-colors hover:bg-white/25"
          >
            <X className="h-5 w-5" />
          </button>
          <img
            src={src}
            alt={alt}
            className={cn(
              "max-h-[90vh] max-w-[90vw] cursor-zoom-out rounded object-contain",
            )}
          />
        </div>,
        document.body,
      )}
    </>
  );
}
