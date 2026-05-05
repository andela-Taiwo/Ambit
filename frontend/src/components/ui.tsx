import {
  createContext,
  useEffect,
  useId,
  useRef,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type JSX,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from 'react';
import { createPortal } from 'react-dom';

import { ApiError } from '@/api/client';
import { cx } from '@/lib/cx';

// --- buttons --------------------------------------------------------------

type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost';
type ButtonSize = 'sm' | 'md';

const buttonStyles: Record<ButtonVariant, string> = {
  primary:
    'bg-slate-900 text-white hover:bg-slate-700 focus-visible:outline-slate-900 disabled:bg-slate-400',
  secondary:
    'border border-slate-300 bg-white text-slate-800 hover:bg-slate-50 focus-visible:outline-slate-500',
  danger:
    'bg-red-600 text-white hover:bg-red-500 focus-visible:outline-red-600 disabled:bg-red-300',
  ghost: 'text-slate-700 hover:bg-slate-100 focus-visible:outline-slate-500',
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  isLoading?: boolean;
}

export const Button = ({
  variant = 'primary',
  size = 'md',
  isLoading = false,
  disabled,
  className,
  children,
  type = 'button',
  ...props
}: ButtonProps): JSX.Element => (
  <button
    {...props}
    type={type}
    disabled={disabled === true || isLoading}
    aria-busy={isLoading || undefined}
    className={cx(
      'inline-flex items-center justify-center gap-2 rounded-md font-medium transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed',
      size === 'sm' ? 'px-3 py-1.5 text-sm' : 'px-4 py-2 text-sm',
      buttonStyles[variant],
      className,
    )}
  >
    {isLoading ? <Spinner label="Working" /> : null}
    {children}
  </button>
);

export const Spinner = ({
  label = 'Loading',
  decorative = false,
}: {
  label?: string;
  decorative?: boolean;
}): JSX.Element => (
  <span
    {...(decorative ? { 'aria-hidden': true } : { role: 'status', 'aria-label': label })}
    className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"
  />
);

// --- layout ---------------------------------------------------------------

export const Card = ({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}): JSX.Element => (
  <section className={cx('rounded-lg border border-slate-200 bg-white p-6 shadow-sm', className)}>
    {children}
  </section>
);

export const PageHeader = ({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
}): JSX.Element => (
  <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
    <div>
      <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{title}</h1>
      {description !== undefined ? (
        <p className="mt-1 text-sm text-slate-600">{description}</p>
      ) : null}
    </div>
    {actions !== undefined ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
  </div>
);

export const StatCard = ({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}): JSX.Element => (
  <Card className="min-w-0">
    <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
    <p className="mt-2 truncate text-2xl font-semibold text-slate-900">{value}</p>
    {hint !== undefined ? <p className="mt-1 text-xs text-slate-500">{hint}</p> : null}
  </Card>
);

// --- form fields ----------------------------------------------------------

interface FieldShellProps {
  id: string;
  label: string;
  hint?: string;
  error?: string;
  children: ReactNode;
}

const FieldShell = ({ id, label, hint, error, children }: FieldShellProps): JSX.Element => (
  <div className="space-y-1">
    <label htmlFor={id} className="block text-sm font-medium text-slate-700">
      {label}
    </label>
    {children}
    {hint !== undefined ? (
      <p id={`${id}-hint`} className="text-xs text-slate-500">
        {hint}
      </p>
    ) : null}
    {error !== undefined ? (
      <p id={`${id}-error`} role="alert" className="text-xs font-medium text-red-700">
        {error}
      </p>
    ) : null}
  </div>
);

const controlClasses = (error: string | undefined): string =>
  cx(
    'block w-full rounded-md border bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:outline-none focus:ring-2',
    error !== undefined
      ? 'border-red-400 focus:border-red-500 focus:ring-red-200'
      : 'border-slate-300 focus:border-slate-500 focus:ring-slate-200',
  );

export interface TextInputProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  hint?: string;
  error?: string;
}

export const TextInput = ({ label, hint, error, id, ...props }: TextInputProps): JSX.Element => {
  const generatedId = useId();
  const fieldId = id ?? generatedId;
  const ids = { id: fieldId, errorId: `${fieldId}-error` };
  return (
    <FieldShell
      id={ids.id}
      label={label}
      {...(hint !== undefined ? { hint } : {})}
      {...(error !== undefined ? { error } : {})}
    >
      <input
        {...props}
        id={ids.id}
        aria-invalid={error !== undefined}
        aria-describedby={error !== undefined ? ids.errorId : undefined}
        className={controlClasses(error)}
      />
    </FieldShell>
  );
};

export interface SelectInputProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label: string;
  hint?: string;
  error?: string;
}

export const SelectInput = ({
  label,
  hint,
  error,
  id,
  children,
  ...props
}: SelectInputProps): JSX.Element => {
  const generatedId = useId();
  const fieldId = id ?? generatedId;
  const ids = { id: fieldId, errorId: `${fieldId}-error` };
  return (
    <FieldShell
      id={ids.id}
      label={label}
      {...(hint !== undefined ? { hint } : {})}
      {...(error !== undefined ? { error } : {})}
    >
      <select
        {...props}
        id={ids.id}
        aria-invalid={error !== undefined}
        aria-describedby={error !== undefined ? ids.errorId : undefined}
        className={controlClasses(error)}
      >
        {children}
      </select>
    </FieldShell>
  );
};

export interface TextAreaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label: string;
  hint?: string;
  error?: string;
}

export const TextAreaInput = ({ label, hint, error, id, ...props }: TextAreaProps): JSX.Element => {
  const generatedId = useId();
  const fieldId = id ?? generatedId;
  const ids = { id: fieldId, errorId: `${fieldId}-error` };
  return (
    <FieldShell
      id={ids.id}
      label={label}
      {...(hint !== undefined ? { hint } : {})}
      {...(error !== undefined ? { error } : {})}
    >
      <textarea
        {...props}
        id={ids.id}
        aria-invalid={error !== undefined}
        aria-describedby={error !== undefined ? ids.errorId : undefined}
        className={controlClasses(error)}
      />
    </FieldShell>
  );
};

// --- feedback -------------------------------------------------------------

type AlertVariant = 'error' | 'success' | 'info' | 'warning';

const alertStyles: Record<AlertVariant, string> = {
  error: 'border-red-200 bg-red-50 text-red-800',
  success: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  info: 'border-sky-200 bg-sky-50 text-sky-800',
  warning: 'border-amber-200 bg-amber-50 text-amber-900',
};

export const Alert = ({
  variant = 'info',
  children,
}: {
  variant?: AlertVariant;
  children: ReactNode;
}): JSX.Element => (
  <div
    role={variant === 'error' ? 'alert' : 'status'}
    className={cx('rounded-md border px-4 py-3 text-sm', alertStyles[variant])}
  >
    {children}
  </div>
);

export const ErrorAlert = ({ error }: { error: unknown }): JSX.Element | null => {
  if (error === null || error === undefined) return null;
  const message =
    error instanceof ApiError || error instanceof Error
      ? error.message
      : typeof error === 'string'
        ? error
        : 'Something went wrong';
  return <Alert variant="error">{message}</Alert>;
};

export const EmptyState = ({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}): JSX.Element => (
  <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-8 text-center">
    <p className="text-sm font-medium text-slate-800">{title}</p>
    {description !== undefined ? (
      <p className="mt-1 text-sm text-slate-600">{description}</p>
    ) : null}
    {action !== undefined ? <div className="mt-4">{action}</div> : null}
  </div>
);

export const LoadingState = ({ label = 'Loading…' }: { label?: string }): JSX.Element => (
  <div role="status" className="flex items-center gap-2 py-8 text-sm text-slate-600">
    <Spinner label={label} decorative />
    <span>{label}</span>
  </div>
);

type BadgeTone = 'neutral' | 'success' | 'warning' | 'danger' | 'info';

const badgeStyles: Record<BadgeTone, string> = {
  neutral: 'bg-slate-100 text-slate-700',
  success: 'bg-emerald-100 text-emerald-800',
  warning: 'bg-amber-100 text-amber-900',
  danger: 'bg-red-100 text-red-800',
  info: 'bg-sky-100 text-sky-800',
};

export const Badge = ({
  tone = 'neutral',
  children,
}: {
  tone?: BadgeTone;
  children: ReactNode;
}): JSX.Element => (
  <span
    className={cx('inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium', badgeStyles[tone])}
  >
    {children}
  </span>
);

export const ProgressBar = ({
  value,
  tone = 'success',
  label,
}: {
  value: number;
  tone?: 'success' | 'warning' | 'danger';
  label: string;
}): JSX.Element => {
  const clamped = Math.max(0, Math.min(100, value));
  const colors = { success: 'bg-emerald-500', warning: 'bg-amber-500', danger: 'bg-red-500' };
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(clamped)}
      className="h-2 w-full overflow-hidden rounded-full bg-slate-200"
    >
      <div
        className={cx('h-full rounded-full transition-all', colors[tone])}
        style={{ width: `${String(clamped)}%` }}
      />
    </div>
  );
};

// --- modal ----------------------------------------------------------------

interface ModalContextValue {
  onClose: () => void;
}

const ModalContext = createContext<ModalContextValue>({ onClose: () => undefined });

export const Modal = ({
  open,
  title,
  onClose,
  children,
  footer,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
}): JSX.Element | null => {
  const titleId = useId();
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return undefined;
    const previous = document.activeElement;
    const onKeyDown = (event: KeyboardEvent): void => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== 'Tab' || panelRef.current === null) return;
      const focusable = panelRef.current.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      );
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (first === undefined || last === undefined) return;
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', onKeyDown);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    panelRef.current?.querySelector<HTMLElement>('input, select, textarea, button')?.focus();
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      document.body.style.overflow = overflow;
      if (previous instanceof HTMLElement) previous.focus();
    };
  }, [open, onClose]);

  if (!open) return null;

  return createPortal(
    <ModalContext.Provider value={{ onClose }}>
      <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/50 p-4 sm:items-center">
        <div
          ref={panelRef}
          role="dialog"
          aria-modal="true"
          aria-labelledby={titleId}
          className="w-full max-w-lg rounded-lg bg-white p-6 shadow-xl"
        >
          <div className="mb-4 flex items-start justify-between gap-4">
            <h2 id={titleId} className="text-lg font-semibold text-slate-900">
              {title}
            </h2>
            <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close dialog">
              ✕
            </Button>
          </div>
          <div className="space-y-4">{children}</div>
          {footer !== undefined ? (
            <div className="mt-6 flex justify-end gap-2">{footer}</div>
          ) : null}
        </div>
      </div>
    </ModalContext.Provider>,
    document.body,
  );
};

export const ConfirmDialog = ({
  open,
  title,
  message,
  confirmLabel = 'Delete',
  onConfirm,
  onCancel,
  isLoading = false,
}: {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
  isLoading?: boolean;
}): JSX.Element => (
  <Modal
    open={open}
    title={title}
    onClose={onCancel}
    footer={
      <>
        <Button variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
        <Button variant="danger" onClick={onConfirm} isLoading={isLoading}>
          {confirmLabel}
        </Button>
      </>
    }
  >
    <p className="text-sm text-slate-700">{message}</p>
  </Modal>
);

// --- pagination -----------------------------------------------------------

export const Pagination = ({
  total,
  limit,
  offset,
  onChange,
}: {
  total: number;
  limit: number;
  offset: number;
  onChange: (offset: number) => void;
}): JSX.Element => {
  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + limit, total);
  return (
    <nav aria-label="Pagination" className="flex items-center justify-between gap-3 py-3 text-sm">
      <p className="text-slate-600">
        Showing {from}–{to} of {total}
      </p>
      <div className="flex gap-2">
        <Button
          variant="secondary"
          size="sm"
          disabled={offset === 0}
          onClick={() => onChange(Math.max(0, offset - limit))}
        >
          Previous
        </Button>
        <Button
          variant="secondary"
          size="sm"
          disabled={offset + limit >= total}
          onClick={() => onChange(offset + limit)}
        >
          Next
        </Button>
      </div>
    </nav>
  );
};

// --- misc -----------------------------------------------------------------
