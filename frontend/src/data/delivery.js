/**
 * მიწოდების წესები mock რეჟიმისთვის — `GET /delivery`-ის პასუხის ფორმით.
 *
 * mockApi ცრუ backend-ია და მხოლოდ ის კითხულობს ამ ფაილს; http ბილდში ის
 * საერთოდ არ ხვდება. ნამდვილი წესები backend-ის app/services/delivery.py-შია —
 * იქ შეცვლისას აქაც გაასწორეთ, თორემ mock რეჟიმი ძველ ფასებს აჩვენებს.
 */
export const deliveryRules = {
  cities: [
    { name: 'თბილისი', fee: 8 },
    { name: 'რუსთავი', fee: 5 },
  ],
  freeFrom: 50,
  currency: 'GEL',
};
