import { INFO_PAGES, SHOP_FACTS } from '../../constants/index.js';
import InfoPage, { InfoSection } from './InfoPage.jsx';
import DeliveryTable from './DeliveryTable.jsx';

/** მიწოდების პირობები — ქალაქები და ფასები `GET /delivery`-დან. */
export default function DeliveryTerms() {
  const { deliveryDays } = SHOP_FACTS;

  return (
    <InfoPage
      page={INFO_PAGES.delivery}
      description="სად ვაწვდით, რა ღირს მიწოდება, როდის არის უფასო და როგორ ხდება გადახდა."
    >
      <InfoSection title="სად ვაწვდით">
        <p>ამჟამად პროდუქციას ვაწვდით ქვემოთ ჩამოთვლილ ქალაქებში.</p>
      </InfoSection>

      <InfoSection title="მიწოდების ღირებულება">
        <DeliveryTable />
        <p>
          მიწოდების ღირებულება ჩანს კალათასა და შეკვეთის გაფორმებისას, შეკვეთის დადასტურებამდე.
        </p>
      </InfoSection>

      <InfoSection title="მიწოდების ვადა">
        <p>
          {deliveryDays && `შეკვეთა მიიტანება ${deliveryDays} სამუშაო დღეში. `}
          მიწოდებას ახორციელებს საკურიერო სერვისი.
        </p>
      </InfoSection>

      <InfoSection title="გადახდა">
        <p>
          ამჟამად გადახდა ხდება ნაღდი ანგარიშსწორებით, პროდუქტის მიღებისას. ონლაინ ბარათით
          გადახდა მალე დაემატება.
        </p>
      </InfoSection>

      <InfoSection title="პროდუქტის მიღებისას">
        <p>
          გთხოვთ, კურიერთან შეამოწმოთ ამანათის მთლიანობა. დაზიანებული შეფუთვის შემთხვევაში, უარი
          თქვით მიღებაზე და დაგვიკავშირდით.
        </p>
      </InfoSection>
    </InfoPage>
  );
}
