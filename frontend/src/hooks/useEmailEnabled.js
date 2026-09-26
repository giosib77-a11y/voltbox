import { useDeliveryRules } from './useDeliveryRules.js';

/**
 * შეუძლია თუ არა მაღაზიას ელფოსტის გაგზავნა — `GET /delivery`-ის `features.email`.
 *
 * false, სანამ პასუხი არ მოსულა და როცა ვერ ჩაიტვირთა: გვერდმა არ უნდა
 * დაჰპირდეს წერილს, რომლის გაგზავნაც არ ვიცით. checkout-ის სტუმრის ელფოსტის
 * ველი და შესვლის გვერდზე „დაგავიწყდათ პაროლი?" ბმული ამით იმალება.
 *
 * მოთხოვნა ცალკე არ იგზავნება — წესები სესიაზე ერთხელ იტვირთება და footer
 * მათ ყველა გვერდზე უკვე ითხოვს.
 */
export function useEmailEnabled() {
  const { rules } = useDeliveryRules();
  return rules?.features?.email === true;
}
