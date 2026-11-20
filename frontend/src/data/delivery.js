/**
 * მიწოდების წესები mock რეჟიმისთვის — `GET /delivery`-ის პასუხის ფორმით.
 *
 * mockApi ცრუ backend-ია და მხოლოდ ის კითხულობს ამ ფაილს; http ბილდში ის
 * საერთოდ არ ხვდება. ნამდვილი წესები backend-ის app/services/delivery.py-შია —
 * იქ შეცვლისას აქაც გაასწორეთ, თორემ mock რეჟიმი ძველ ფასებს აჩვენებს.
 * backend/tests/test_delivery_payment.py ამ ფაილს CITY_FEES-ს ადარებს.
 */
export const deliveryRules = {
  cities: [
    { name: 'თბილისი', fee: 11, cardOnDelivery: true },
    { name: 'რუსთავი', fee: 7, cardOnDelivery: true },
  ],
  freeFrom: 100,
  currency: 'GEL',
  // mock რეჟიმი წერილს ვერ აგზავნის
  features: { email: false },
};
