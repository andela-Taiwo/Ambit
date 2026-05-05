import type { JSX } from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';

import {
  Alert,
  Badge,
  Button,
  ConfirmDialog,
  EmptyState,
  ErrorAlert,
  LoadingState,
  Modal,
  Pagination,
  ProgressBar,
  SelectInput,
  TextAreaInput,
  TextInput,
} from '@/components/ui';

describe('Button', () => {
  it('renders a button and calls onClick', async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Save</Button>);

    await userEvent.click(screen.getByRole('button', { name: 'Save' }));

    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it('is disabled and busy while loading', () => {
    render(<Button isLoading>Save</Button>);

    const button = screen.getByRole('button', { name: /save/i });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute('aria-busy', 'true');
    expect(screen.getByRole('status', { name: /working/i })).toBeInTheDocument();
  });
});

describe('form fields', () => {
  it('associates a label and error with the input', () => {
    render(
      <TextInput label="Amount" error="Enter an amount" value="" onChange={() => undefined} />,
    );

    const input = screen.getByLabelText('Amount');
    expect(input).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByRole('alert')).toHaveTextContent('Enter an amount');
  });

  it('renders a hint and select options', () => {
    render(
      <SelectInput label="Currency" hint="ISO code">
        <option value="GBP">GBP</option>
      </SelectInput>,
    );

    expect(screen.getByLabelText('Currency')).toBeInTheDocument();
    expect(screen.getByText('ISO code')).toBeInTheDocument();
  });

  it('renders a textarea', () => {
    render(<TextAreaInput label="Notes" />);

    expect(screen.getByLabelText('Notes').tagName).toBe('TEXTAREA');
  });
});

describe('feedback', () => {
  it('renders error, success and info alerts with suitable roles', () => {
    const { rerender } = render(<Alert variant="error">Boom</Alert>);
    expect(screen.getByRole('alert')).toHaveTextContent('Boom');

    rerender(<Alert variant="success">Saved</Alert>);
    expect(screen.getByRole('status')).toHaveTextContent('Saved');
  });

  it('renders an ErrorAlert from an Error and ignores null', () => {
    const { rerender } = render(<ErrorAlert error={new Error('Network failed')} />);
    expect(screen.getByRole('alert')).toHaveTextContent('Network failed');

    rerender(<ErrorAlert error={null} />);
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('renders badges with tone classes', () => {
    render(<Badge tone="danger">Over</Badge>);
    expect(screen.getByText('Over')).toHaveClass('bg-red-100');
  });

  it('renders a labelled progress bar clamped to 0–100', () => {
    render(<ProgressBar value={140} tone="danger" label="Groceries budget" />);

    const bar = screen.getByRole('progressbar', { name: 'Groceries budget' });
    expect(bar).toHaveAttribute('aria-valuenow', '100');
  });

  it('renders empty and loading states', () => {
    const { rerender } = render(<EmptyState title="Nothing yet" description="Add one" />);
    expect(screen.getByText('Nothing yet')).toBeInTheDocument();
    expect(screen.getByText('Add one')).toBeInTheDocument();

    rerender(<LoadingState label="Fetching" />);
    expect(screen.getByRole('status')).toHaveTextContent('Fetching');
  });
});

describe('Modal', () => {
  const Harness = (): JSX.Element => {
    const [open, setOpen] = useState(true);
    return (
      <>
        <button type="button" onClick={() => setOpen(true)}>
          Open
        </button>
        <Modal
          open={open}
          title="Edit account"
          onClose={() => setOpen(false)}
          footer={<Button onClick={() => setOpen(false)}>Done</Button>}
        >
          <TextInput label="Name" />
        </Modal>
      </>
    );
  };

  it('renders a dialog with an accessible title and closes on Escape', async () => {
    render(<Harness />);

    expect(screen.getByRole('dialog', { name: 'Edit account' })).toBeInTheDocument();
    await userEvent.keyboard('{Escape}');

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('closes via the close button and footer', async () => {
    render(<Harness />);

    await userEvent.click(screen.getByRole('button', { name: /close dialog/i }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Open' }));
    await userEvent.click(screen.getByRole('button', { name: 'Done' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('renders a confirm dialog and confirms', async () => {
    const onConfirm = vi.fn();
    render(
      <ConfirmDialog
        open
        title="Delete account?"
        message="This cannot be undone."
        onConfirm={onConfirm}
        onCancel={() => undefined}
      />,
    );

    await userEvent.click(screen.getByRole('button', { name: 'Delete' }));

    expect(onConfirm).toHaveBeenCalledTimes(1);
  });
});

describe('Pagination', () => {
  it('shows the visible range and moves pages', async () => {
    const onChange = vi.fn();
    render(<Pagination total={120} limit={50} offset={50} onChange={onChange} />);

    expect(screen.getByText('Showing 51–100 of 120')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Next' }));
    expect(onChange).toHaveBeenCalledWith(100);
    await userEvent.click(screen.getByRole('button', { name: 'Previous' }));
    expect(onChange).toHaveBeenCalledWith(0);
  });

  it('disables boundaries at the edges', () => {
    render(<Pagination total={10} limit={50} offset={0} onChange={() => undefined} />);

    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled();
  });
});

describe('component variants', () => {
  it('renders every button variant and size', () => {
    const { rerender } = render(
      <Button variant="secondary" size="sm">
        Secondary
      </Button>,
    );
    expect(screen.getByRole('button', { name: 'Secondary' })).toBeInTheDocument();
    rerender(<Button variant="danger">Danger</Button>);
    expect(screen.getByRole('button', { name: 'Danger' })).toBeInTheDocument();
    rerender(<Button variant="ghost">Ghost</Button>);
    expect(screen.getByRole('button', { name: 'Ghost' })).toBeInTheDocument();
    rerender(<Button disabled>Disabled</Button>);
    expect(screen.getByRole('button', { name: 'Disabled' })).toBeDisabled();
  });

  it('renders hints without errors and accepts an explicit id', () => {
    render(<TextInput id="custom-amount" label="Amount" hint="In major units" />);

    expect(screen.getByLabelText('Amount')).toHaveAttribute('id', 'custom-amount');
    expect(screen.getByText('In major units')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('renders select and textarea errors', () => {
    render(
      <SelectInput label="Type" error="Choose one">
        <option value="a">A</option>
      </SelectInput>,
    );
    expect(screen.getByLabelText('Type')).toHaveAttribute('aria-invalid', 'true');

    render(<TextAreaInput label="Notes" error="Too long" />);
    expect(screen.getByLabelText('Notes')).toHaveAttribute('aria-invalid', 'true');
  });

  it('renders default badge tone and warning progress', () => {
    render(
      <>
        <Badge>Neutral</Badge>
        <ProgressBar value={50} tone="warning" label="Warning budget" />
      </>,
    );
    expect(screen.getByText('Neutral')).toHaveClass('bg-slate-100');
    expect(screen.getByRole('progressbar', { name: 'Warning budget' })).toHaveAttribute(
      'aria-valuenow',
      '50',
    );
  });

  it('renders info and warning alerts', () => {
    const { rerender } = render(<Alert variant="info">Info</Alert>);
    expect(screen.getByRole('status')).toHaveTextContent('Info');
    rerender(<Alert variant="warning">Warning</Alert>);
    expect(screen.getByRole('status')).toHaveTextContent('Warning');
  });

  it('renders an empty state with an action', () => {
    render(<EmptyState title="No data" action={<Button>Add</Button>} />);
    expect(screen.getByRole('button', { name: 'Add' })).toBeInTheDocument();
  });

  it('renders a modal without a footer', async () => {
    render(
      <Modal open title="No footer" onClose={() => undefined}>
        <p>Body</p>
      </Modal>,
    );
    expect(screen.getByRole('dialog', { name: 'No footer' })).toBeInTheDocument();
    await userEvent.keyboard('{Escape}');
  });

  it('handles an empty pagination total', () => {
    render(<Pagination total={0} limit={50} offset={0} onChange={() => undefined} />);
    expect(screen.getByText('Showing 0–0 of 0')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled();
  });
});
