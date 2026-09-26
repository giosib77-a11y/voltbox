import { INFO_PAGES, SHOP_FACTS } from '../../constants/index.js';
import { useEmailEnabled } from '../../hooks/useEmailEnabled.js';
import InfoPage, { InfoSection } from './InfoPage.jsx';
import { ContactInline } from './Contact.jsx';

/**
 * კონფიდენციალურობის პოლიტიკა.
 *
 * ყოველი მტკიცება კოდს ემთხვევა და InfoPages.test.jsx ამას ამოწმებს:
 * რა ინახება ბრაუზერში (STORAGE_KEYS, services/httpApi.js-ის
 * GUEST_ORDERS_KEY), რა მიდის Telegram-ში (backend/app/services/telegram.py),
 * რას ითხოვს რეგისტრაცია. ერთ მხარეს ცვლილება მეორესაც მოითხოვს.
 *
 * Resend სიაში მხოლოდ მაშინ ჩანს, როცა მაღაზია წერილს მართლა აგზავნის
 * (`useEmailEnabled`) — მანამდე მას მყიდველის არცერთი მონაცემი არ ეგზავნება.
 */
export default function Privacy() {
  const emailEnabled = useEmailEnabled();
  const { legalEntity } = SHOP_FACTS;

  return (
    <InfoPage
      page={INFO_PAGES.privacy}
      description="რა პერსონალურ მონაცემებს ვაგროვებთ, რისთვის ვიყენებთ, ვის ვუზიარებთ და რა უფლებები გაქვთ."
    >
      {legalEntity && (
        <InfoSection title="ვინ ვართ">
          <dl className="grid gap-x-4 gap-y-1.5 sm:grid-cols-[auto_1fr]">
            <dt className="font-semibold text-ink-900">დასახელება</dt>
            <dd>{legalEntity.name}</dd>
            <dt className="font-semibold text-ink-900">საიდენტიფიკაციო კოდი</dt>
            <dd>{legalEntity.idCode}</dd>
            <dt className="font-semibold text-ink-900">იურიდიული მისამართი</dt>
            <dd>{legalEntity.address}</dd>
          </dl>
        </InfoSection>
      )}

      <InfoSection title="რა მონაცემებს ვაგროვებთ">
        <p>
          <strong className="font-semibold text-ink-900">შეკვეთისას:</strong> სახელი და გვარი,
          ტელეფონის ნომერი, მიწოდების ქალაქი და მისამართი, ელფოსტა (არასავალდებულო).
        </p>
        <p>
          <strong className="font-semibold text-ink-900">რეგისტრაციისას:</strong> სახელი და
          გვარი, ელფოსტა და პაროლი, შენახული მისამართები, შეკვეთების ისტორია. პაროლს ვინახავთ
          მხოლოდ დაშიფრული სახით — ჩვენ ის არ ვიცით და ვერ ვნახავთ.
        </p>
        <p>
          <strong className="font-semibold text-ink-900">ტექნიკური მონაცემები:</strong> IP მისამართი
          — უსაფრთხოებისთვის, მაგ. შესვლის მცდელობების შეზღუდვისთვის, მოკლე ვადით.
        </p>
      </InfoSection>

      <InfoSection title="რისთვის ვიყენებთ">
        <p>
          შეკვეთის შესრულება და მიწოდება, თქვენთან დაკავშირება შეკვეთის შესახებ, ანგარიშის მართვა
          და საიტის უსაფრთხოება. თქვენს მონაცემებს არ ვყიდით და რეკლამისთვის არ ვიყენებთ.
        </p>
      </InfoSection>

      <InfoSection title="ვის ვუზიარებთ">
        <p>მხოლოდ იმას, ვინც შეკვეთის შესასრულებლად აუცილებელია:</p>
        <ul className="list-disc space-y-1.5 pl-5">
          <li>საკურიერო სერვისი — სახელი, ტელეფონი, მისამართი — მიწოდებისთვის</li>
          <li>Render — საიტის ჰოსტინგი</li>
          <li>Supabase — მონაცემთა ბაზა, ევროკავშირში</li>
          {emailEnabled && <li>Resend — ელფოსტა, შეკვეთის დადასტურებისთვის</li>}
        </ul>
        <p>
          შეკვეთის შესახებ შიდა შეტყობინებაში, რომელსაც მაღაზია იღებს, თქვენი პერსონალური
          მონაცემები არ იგზავნება — მხოლოდ შეკვეთის ნომერი, პროდუქტების ღირებულება, მიწოდების
          საფასური, ჯამი, ნივთების რაოდენობა და ბმული შეკვეთაზე მაღაზიის მართვის პანელში.
        </p>
      </InfoSection>

      <InfoSection title="ბრაუზერში შენახული მონაცემები">
        <p>
          საიტი ბრაუზერში ინახავს მხოლოდ იმას, რაც მუშაობისთვის საჭიროა: კალათის შიგთავსს, თემის
          არჩევანს, შესვლის სესიას და ბოლო ძებნებს. შეკვეთის შემდეგ — შეკვეთის ნომერს და
          მითითებულ ტელეფონის ნომერს, რომ ამავე ბრაუზერიდან შეკვეთის გვერდი გაიხსნას. სარეკლამო
          ან თვალთვალის cookie-ებს არ ვიყენებთ.
        </p>
      </InfoSection>

      <InfoSection title="რამდენ ხანს ვინახავთ">
        <p>
          შეკვეთის მონაცემებს — კანონით დადგენილი ვადით, საგადასახადო აღრიცხვისთვის. ანგარიშის
          მონაცემებს — ანგარიშის წაშლამდე.
        </p>
      </InfoSection>

      <InfoSection title="თქვენი უფლებები">
        <p>
          საქართველოს კანონის „პერსონალურ მონაცემთა დაცვის შესახებ“ შესაბამისად, გაქვთ უფლება
          გაეცნოთ თქვენს მონაცემებს, მოითხოვოთ მათი შესწორება ან წაშლა, და გაიწვიოთ თანხმობა.
          მოთხოვნისთვის დაგვიკავშირდით: <ContactInline />. საჩივრის შემთხვევაში შეგიძლიათ
          მიმართოთ პერსონალურ მონაცემთა დაცვის სამსახურს.
        </p>
      </InfoSection>
    </InfoPage>
  );
}
