// Forma de pago: de contado (1) o en N cuotas. Lo usan la cotización y la compra.
export const INSTALLMENT_CHOICES = [1, 2, 3, 4, 6, 9, 12];

export const installmentsLabel = (n: number | null | undefined) =>
  n == null ? "sin indicar" : n === 1 ? "de contado" : `${n} cuotas`;

export function InstallmentPicker({ value, onChange, disabled }: { value: number; onChange: (n: number) => void; disabled?: boolean }) {
  return (
    <div className="installment-picker" role="radiogroup" aria-label="Forma de pago">
      {INSTALLMENT_CHOICES.map((n) => (
        <button
          key={n}
          type="button"
          role="radio"
          aria-checked={value === n}
          className={value === n ? "selected" : ""}
          onClick={() => onChange(n)}
          disabled={disabled}
        >
          {n === 1 ? "Contado" : `${n} cuotas`}
        </button>
      ))}
    </div>
  );
}
