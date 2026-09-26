import ErrorState from '../../components/common/ErrorState.jsx';
import { Skeleton } from '../../components/common/Skeleton.jsx';
import { TEXT } from '../../constants/index.js';
import { useDeliveryRules } from '../../hooks/useDeliveryRules.js';
import { formatPrice } from '../../utils/format.js';

/**
 * ქალაქები, მათი ტარიფი და უფასო მიწოდების ზღვარი — `GET /delivery`-დან.
 *
 * ციფრი აქ არცერთი არ წერია: ფასი backend-ის app/services/delivery.py-ში
 * იცვლება და ეს ცხრილი მას კალათასთან და checkout-თან ერთად მიჰყვება. სანამ
 * წესები არ მოსულა, ცხრილის ადგილას skeleton დგას და არა ძველი რიცხვი.
 */
export default function DeliveryTable() {
  const { rules, error, reload } = useDeliveryRules();

  if (error) {
    return (
      <ErrorState
        description="მიწოდების ფასები ვერ ჩაიტვირთა."
        onRetry={reload}
        className="py-8"
      />
    );
  }

  if (!rules) return <Skeleton className="h-36 w-full" rounded="rounded-card" />;

  return (
    <div className="overflow-hidden rounded-card border border-ink-200 bg-surface">
      <table className="w-full text-left text-sm">
        <caption className="sr-only">მიწოდების ღირებულება ქალაქების მიხედვით</caption>
        <thead className="bg-ink-100 text-ink-700">
          <tr>
            <th scope="col" className="px-4 py-2.5 font-semibold">
              ქალაქი
            </th>
            <th scope="col" className="px-4 py-2.5 text-right font-semibold">
              მიწოდება
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-ink-200">
          {rules.cities.map((city) => (
            <tr key={city.name}>
              <th scope="row" className="px-4 py-3 font-medium text-ink-900">
                {city.name}
              </th>
              <td className="px-4 py-3 text-right tabular-nums text-ink-900">
                {formatPrice(city.fee)}
              </td>
            </tr>
          ))}
          <tr className="bg-primary-50">
            <th scope="row" className="px-4 py-3 font-medium text-primary-800">
              შეკვეთა {formatPrice(rules.freeFrom)}-დან
            </th>
            <td className="px-4 py-3 text-right font-semibold text-primary-800">{TEXT.free}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
