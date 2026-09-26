import { useId } from 'react';
import { INFO_PAGES, SHOP_FACTS } from '../../constants/index.js';
import InfoPage, { InfoSection } from './InfoPage.jsx';
import { ContactInline } from './Contact.jsx';

/** დაბრუნება და გარანტია. */
export default function ReturnsWarranty() {
  const { returnPickup, warrantyPeriod } = SHOP_FACTS;
  const conditionsId = useId();
  const stepsId = useId();

  return (
    <InfoPage
      page={INFO_PAGES.returns}
      description="ონლაინ შეძენილი პროდუქტის დაბრუნება 14 დღეში, დეფექტური პროდუქტი და გარანტია."
    >
      <InfoSection title="დაბრუნება მიზეზის გარეშე">
        <p>
          ონლაინ შეძენილი პროდუქტის დაბრუნება შეგიძლიათ მიღებიდან 14 დღის განმავლობაში, მიზეზის
          მითითების გარეშე, საქართველოს კანონის „მომხმარებლის უფლებების დაცვის შესახებ“
          შესაბამისად.
        </p>

        <p id={conditionsId} className="font-semibold text-ink-900">
          პირობები:
        </p>
        <ul aria-labelledby={conditionsId} className="list-disc space-y-1.5 pl-5">
          <li>პროდუქტი არ უნდა იყოს გამოყენებული და დაზიანებული</li>
          <li>დაცული უნდა იყოს ორიგინალი შეფუთვა, აქსესუარები და დოკუმენტაცია</li>
        </ul>

        <p>
          <strong className="font-semibold text-ink-900">გამონაკლისი:</strong> ჰიგიენური მიზეზით,
          ყურსასმენები და სხვა პროდუქტი, რომელიც სხეულთან უშუალო კონტაქტში გამოიყენება, არ
          დაბრუნდება, თუ მიწოდების შემდეგ ქარხნული შეფუთვა გახსნილია.
        </p>

        <p id={stepsId} className="font-semibold text-ink-900">
          როგორ დავაბრუნოთ:
        </p>
        <ol aria-labelledby={stepsId} className="list-decimal space-y-1.5 pl-5">
          <li>
            დაგვიკავშირდით და მიუთითეთ შეკვეთის ნომერი — <ContactInline />
          </li>
          {returnPickup && <li>{returnPickup}</li>}
          <li>
            თანხას დაგიბრუნებთ 14 დღის განმავლობაში, პროდუქტის მიღებისა და შემოწმების შემდეგ
          </li>
        </ol>

        <p>
          დაბრუნების მიწოდების ხარჯი მყიდველს ეკისრება, გარდა იმ შემთხვევისა, როცა პროდუქტი
          დეფექტურია ან შეკვეთისგან განსხვავებულია.
        </p>

        <p>
          ნაღდი ანგარიშსწორებით გადახდილ თანხას დაგიბრუნებთ საბანკო გადარიცხვით თქვენ მიერ
          მითითებულ ანგარიშზე.
        </p>
      </InfoSection>

      <InfoSection title="დეფექტური პროდუქტი და გარანტია">
        <p>
          თუ პროდუქტი დეფექტურია ან არ შეესაბამება აღწერას, გაქვთ უფლება მოითხოვოთ შეკეთება,
          შეცვლა ან თანხის დაბრუნება, კანონის შესაბამისად.
        </p>

        {warrantyPeriod && <p>პროდუქტზე ვრცელდება გარანტია, ვადით {warrantyPeriod}.</p>}

        <p>
          გარანტია არ ვრცელდება დაზიანებაზე, რომელიც გამოწვეულია არასწორი გამოყენებით, მექანიკური
          ზემოქმედებით ან სითხით.
        </p>
      </InfoSection>
    </InfoPage>
  );
}
