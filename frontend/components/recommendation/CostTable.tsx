"use client";

import type { CostBreakdown } from "@/lib/types";

const rupees = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });

function inr(value: string): string {
  return `₹${rupees.format(Number(value))}`;
}

/**
 * The full calculation, always available.
 *
 * BUILD.md section 33: never hide the working. Imputed lines are called out
 * explicitly, because a substituted worst-case figure is not the same claim as
 * a published one.
 */
export function CostTable({ cost }: { cost: CostBreakdown }) {
  return (
    <div className="space-y-3">
      <table className="w-full text-sm">
        <caption className="sr-only">Estimated card fees over {cost.duration_months} months</caption>
        <tbody>
          {cost.components.map((component) => (
            <tr
              key={`${component.fee_type}-${component.label}`}
              className="border-b border-slate-100 last:border-0 dark:border-slate-800"
            >
              <th scope="row" className="py-2 pr-3 text-left font-normal align-top">
                <span className="text-slate-800 dark:text-slate-200">{component.label}</span>
                <span className="block text-xs text-slate-500 dark:text-slate-400">
                  {component.basis}
                </span>
                {component.is_imputed && component.imputation_note && (
                  <span className="mt-1 block text-xs text-amber-700 dark:text-amber-500">
                    {component.imputation_note}
                  </span>
                )}
              </th>
              <td className="py-2 text-right align-top tabular-nums text-slate-900 dark:text-slate-100">
                {inr(component.amount_inr)}
              </td>
            </tr>
          ))}
          <tr className="border-t-2 border-slate-200 dark:border-slate-700">
            <th scope="row" className="py-2 pr-3 text-left font-medium text-slate-900 dark:text-slate-100">
              Total over {cost.duration_months} months
              {cost.total_is_lower_bound && (
                <span className="block text-xs font-normal text-amber-700 dark:text-amber-500">
                  At least this much — some charges are unpublished across every card compared.
                </span>
              )}
            </th>
            <td className="py-2 text-right font-medium tabular-nums text-slate-900 dark:text-slate-100">
              {inr(cost.total_inr)}
              {cost.total_spend_currency && cost.spend_currency && (
                <span className="block text-xs font-normal text-slate-500 dark:text-slate-400">
                  ≈ {cost.spend_currency} {rupees.format(Number(cost.total_spend_currency))}
                </span>
              )}
            </td>
          </tr>
        </tbody>
      </table>

      {cost.fx_rate_used && (
        <p className="text-xs text-slate-500 dark:text-slate-400">
          Converted at a mid-market reference rate of {cost.fx_rate_used}. A provider&apos;s own rate
          will differ.
        </p>
      )}

      {cost.assumptions.length > 0 && (
        <details className="text-sm">
          <summary className="cursor-pointer text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200">
            Assumptions behind this estimate ({cost.assumptions.length})
          </summary>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-slate-600 dark:text-slate-400">
            {cost.assumptions.map((assumption) => (
              <li key={assumption}>{assumption}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
