import { useState, type SyntheticEvent, type JSX, type ReactNode } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';

import { Alert, Button, SelectInput, TextInput } from '@/components/ui';
import { SUPPORTED_CURRENCIES } from '@/lib/money';
import { login, register, useAuthStore } from '@/features/auth/store';

const AuthLayout = ({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: ReactNode;
}): JSX.Element => (
  <div className="flex min-h-screen items-center justify-center bg-slate-100 px-4 py-12">
    <div className="grid w-full max-w-4xl overflow-hidden rounded-xl bg-white shadow-xl md:grid-cols-2">
      <div className="hidden bg-slate-900 p-10 text-white md:block">
        <p className="text-sm font-semibold uppercase tracking-widest text-slate-400">
          Finance Tracker
        </p>
        <h1 className="mt-4 text-3xl font-semibold leading-tight">
          Every account, budget and investment in one place.
        </h1>
        <p className="mt-4 text-sm text-slate-300">
          Multi-currency ledger, monthly budgets and investment returns — with exact money
          arithmetic.
        </p>
      </div>
      <div className="p-8 sm:p-10">
        <h2 className="text-2xl font-semibold text-slate-900">{title}</h2>
        <p className="mt-1 text-sm text-slate-600">{subtitle}</p>
        <div className="mt-6">{children}</div>
      </div>
    </div>
  </div>
);

export const LoginPage = (): JSX.Element => {
  const status = useAuthStore((state) => state.status);
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (status === 'authenticated') return <Navigate to="/" replace />;

  const fromState =
    typeof location.state === 'object' && location.state !== null && 'from' in location.state
      ? (location.state as { from?: unknown }).from
      : undefined;
  const nextPath = typeof fromState === 'string' ? fromState : '/';

  const onSubmit = async (event: SyntheticEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
      void navigate(nextPath, { replace: true });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not sign in');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthLayout title="Welcome back" subtitle="Sign in to your finance tracker.">
      <form className="space-y-4" onSubmit={(event) => void onSubmit(event)} noValidate>
        {error !== null ? <Alert variant="error">{error}</Alert> : null}
        <TextInput
          label="Email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
        <TextInput
          label="Password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        <Button type="submit" className="w-full" isLoading={submitting}>
          Sign in
        </Button>
      </form>
      <p className="mt-4 text-sm text-slate-600">
        New here?{' '}
        <Link className="font-medium text-slate-900 underline" to="/register">
          Create an account
        </Link>
      </p>
    </AuthLayout>
  );
};

export const RegisterPage = (): JSX.Element => {
  const status = useAuthStore((state) => state.status);
  const navigate = useNavigate();
  const [displayName, setDisplayName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [baseCurrency, setBaseCurrency] = useState('GBP');
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (status === 'authenticated') return <Navigate to="/" replace />;

  const onSubmit = async (event: SyntheticEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();
    const nextErrors: Record<string, string> = {};
    if (displayName.trim() === '') nextErrors.display_name = 'Enter your name';
    if (password.length < 12) nextErrors.password = 'Use at least 12 characters';
    setFieldErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;

    setError(null);
    setSubmitting(true);
    try {
      await register({
        email,
        password,
        display_name: displayName.trim(),
        base_currency: baseCurrency,
      });
      void navigate('/', { replace: true });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not create the account');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthLayout
      title="Create your account"
      subtitle="Start with your base currency; you can add accounts next."
    >
      <form className="space-y-4" onSubmit={(event) => void onSubmit(event)} noValidate>
        {error !== null ? <Alert variant="error">{error}</Alert> : null}
        <TextInput
          label="Name"
          autoComplete="name"
          required
          value={displayName}
          {...(fieldErrors.display_name !== undefined ? { error: fieldErrors.display_name } : {})}
          onChange={(event) => setDisplayName(event.target.value)}
        />
        <TextInput
          label="Email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
        <TextInput
          label="Password"
          type="password"
          autoComplete="new-password"
          required
          minLength={12}
          hint="At least 12 characters."
          value={password}
          {...(fieldErrors.password !== undefined ? { error: fieldErrors.password } : {})}
          onChange={(event) => setPassword(event.target.value)}
        />
        <SelectInput
          label="Base currency"
          value={baseCurrency}
          onChange={(event) => setBaseCurrency(event.target.value)}
        >
          {SUPPORTED_CURRENCIES.map((code) => (
            <option key={code} value={code}>
              {code}
            </option>
          ))}
        </SelectInput>
        <Button type="submit" className="w-full" isLoading={submitting}>
          Create account
        </Button>
      </form>
      <p className="mt-4 text-sm text-slate-600">
        Already have an account?{' '}
        <Link className="font-medium text-slate-900 underline" to="/login">
          Sign in
        </Link>
      </p>
    </AuthLayout>
  );
};
