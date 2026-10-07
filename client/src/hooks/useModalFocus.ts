import { useEffect, useRef } from 'react';
import type { RefObject } from 'react';

interface ModalFocusOptions {
  open: boolean;
  onDismiss?: () => void;
  initialFocusRef?: RefObject<HTMLElement | null>;
  returnFocusRef?: RefObject<HTMLElement | null>;
}

const focusableSelector = 'a[href], button, input, select, textarea, summary, [tabindex], [contenteditable="true"]';
const activeDialogs = new Set<HTMLElement>();
let focusedDialog: HTMLElement | undefined;

function available(element: HTMLElement): boolean {
  return element.isConnected && !element.matches(':disabled, [aria-disabled="true"]') &&
    !element.closest('[hidden], [inert], [aria-hidden="true"]') &&
    element.getClientRects().length > 0 && getComputedStyle(element).visibility !== 'hidden';
}

function tabbables(dialog: HTMLElement): HTMLElement[] {
  return Array.from(dialog.querySelectorAll<HTMLElement>(focusableSelector))
    .filter(element => element.tabIndex >= 0 && available(element))
    .sort((a, b) => (a.tabIndex > 0 ? a.tabIndex : Infinity) - (b.tabIndex > 0 ? b.tabIndex : Infinity));
}

function layer(dialog: HTMLElement): number {
  let depth = 0;
  for (let element: HTMLElement | null = dialog; element; element = element.parentElement) {
    depth = Math.max(depth, Number.parseInt(getComputedStyle(element).zIndex, 10) || 0);
  }
  return depth;
}

function topDialog(): HTMLElement | undefined {
  let top: HTMLElement | undefined;
  for (const dialog of activeDialogs) {
    if (!available(dialog)) continue;
    if (!top || layer(dialog) > layer(top) ||
      (layer(dialog) === layer(top) && Boolean(top.compareDocumentPosition(dialog) & Node.DOCUMENT_POSITION_FOLLOWING))) {
      top = dialog;
    }
  }
  return top;
}

function focusFirst(dialog: HTMLElement, initial?: HTMLElement | null) {
  focusedDialog = dialog;
  const target = initial && dialog.contains(initial) && available(initial)
    ? initial : tabbables(dialog)[0] || dialog;
  target.focus({ preventScroll: true });
}

/** One focus owner per actual dialog; visual layering also governs stacked dialogs. */
export function useModalFocus<T extends HTMLElement = HTMLDivElement>({ open, onDismiss, initialFocusRef, returnFocusRef }: ModalFocusOptions) {
  const dialogRef = useRef<T>(null);
  const options = useRef({ onDismiss, initialFocusRef, returnFocusRef });
  options.current = { onDismiss, initialFocusRef, returnFocusRef };

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!open || !dialog) return;
    const focused = document.activeElement;
    const opener = focused instanceof HTMLElement && focused.matches(focusableSelector) &&
      !dialog.contains(focused) && available(focused) ? focused : null;
    activeDialogs.add(dialog);

    // Wait until sibling/portal effects register, so a lower dialog never steals focus.
    const frame = requestAnimationFrame(() => {
      if (topDialog() === dialog) focusFirst(dialog, options.current.initialFocusRef?.current);
    });
    const handleKey = (event: KeyboardEvent) => {
      if (topDialog() !== dialog) return;
      if (event.key === 'Escape') {
        event.preventDefault();
        event.stopImmediatePropagation();
        options.current.onDismiss?.();
      } else if (event.key === 'Tab') {
        const controls = tabbables(dialog);
        const index = controls.indexOf(document.activeElement as HTMLElement);
        if (!controls.length || index < 0 || (event.shiftKey ? index === 0 : index === controls.length - 1)) {
          event.preventDefault();
          (event.shiftKey ? controls[controls.length - 1] : controls[0])?.focus({ preventScroll: true });
          if (!controls.length) dialog.focus({ preventScroll: true });
        }
      }
    };
    const containFocus = () => {
      if (topDialog() !== dialog) return;
      focusedDialog = dialog;
      if (!dialog.contains(document.activeElement)) {
        focusFirst(dialog, options.current.initialFocusRef?.current);
      }
    };
    const observer = new MutationObserver(() => {
      if (topDialog() !== dialog) return;
      const current = document.activeElement;
      if (!dialog.contains(current) || (current instanceof HTMLElement && !available(current))) {
        focusFirst(dialog, options.current.initialFocusRef?.current);
      }
    });
    observer.observe(dialog, { subtree: true, childList: true, attributes: true, attributeFilter: ['disabled', 'hidden', 'inert', 'aria-disabled', 'style', 'class'] });
    document.addEventListener('keydown', handleKey, true);
    document.addEventListener('focusin', containFocus, true);

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      document.removeEventListener('keydown', handleKey, true);
      document.removeEventListener('focusin', containFocus, true);
      const wasTop = focusedDialog === dialog || topDialog() === dialog || dialog.contains(document.activeElement);
      activeDialogs.delete(dialog);
      if (focusedDialog === dialog) focusedDialog = undefined;
      queueMicrotask(() => {
        // StrictMode's immediate re-registration and route removal must not steal focus.
        if (activeDialogs.has(dialog) || !wasTop) return;
        const next = topDialog();
        if (next) {
          if (!next.contains(document.activeElement)) focusFirst(next);
          return;
        }
        const fallback = options.current.returnFocusRef?.current;
        const target = opener && available(opener) && !opener.closest('[role="dialog"]')
          ? opener : fallback && available(fallback) ? fallback : null;
        target?.focus({ preventScroll: true });
      });
    };
  }, [open]);

  return dialogRef;
}
