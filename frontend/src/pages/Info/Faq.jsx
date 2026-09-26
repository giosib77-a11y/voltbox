import { Link } from 'react-router';
import { Skeleton } from '../../components/common/Skeleton.jsx';
import { CONTACT, INFO_PAGES, SHOP_FACTS } from '../../constants/index.js';
import { useDeliveryRules } from '../../hooks/useDeliveryRules.js';
import { useEmailEnabled } from '../../hooks/useEmailEnabled.js';
import InfoPage, { InfoSection, TEXT_LINK_CLASS } from './InfoPage.jsx';
import DeliveryTable from './DeliveryTable.jsx';
import { ContactList } from './Contact.jsx';

/**
 * ხშირად დასმული კითხვები.
 *
 * კითხვა, რომლის პასუხიც ჯერ უცნობია (`SHOP_FACTS`-ში `null`), საერთოდ არ
 * ჩანს. „შეკვეთის სტატუსი“ მხოლოდ რეგისტრირებულს პასუხობს: სტუმარს საიტზე
 * შეკვეთის მოსაძებნი გვერდი არ აქვს — იხ. docs/info-pages-todo.md.
 */
export default function Faq() {
  const { rules, loading } = useDeliveryRules();
  const emailEnabled = useEmailEnabled();
  const { deliveryDays } = SHOP_FACTS;

  const items = [
    {
      question: 'როგორ გავაფორმო შეკვეთა?',
      answer: (
        <p>
          დაამატეთ პროდუქტი კალათაში, გადადით კალათაზე და დააჭირეთ „გაფორმებას“. შეავსეთ მიწოდების
          მონაცემები და დაადასტურეთ.
        </p>
      ),
    },
    {
      question: 'რეგისტრაცია სავალდებულოა?',
      answer: (
        <p>
          არა. შეკვეთა შეგიძლიათ რეგისტრაციის გარეშეც. რეგისტრაცია გაძლევთ შეკვეთების ისტორიას და
          შენახულ მისამართს — შემდეგ ჯერზე მისამართი თავისით ჩაიწერება.
        </p>
      ),
    },
    {
      question: 'რა ღირს მიწოდება?',
      answer: <DeliveryTable />,
    },
    {
      question: 'სად ვაწვდით?',
      answer: (
        <p>
          ცხრილში ჩამოთვლილ ქალაქებში
          {rules && `: ${rules.cities.map((city) => city.name).join(', ')}`}.
        </p>
      ),
    },
    {
      question: 'როგორ გადავიხადო?',
      answer: <p>ნაღდი ფულით, პროდუქტის მიღებისას. ონლაინ გადახდა მალე დაემატება.</p>,
    },
    {
      question: 'რამდენ ხანში მომივა?',
      answer: deliveryDays && <p>{deliveryDays} სამუშაო დღეში.</p>,
    },
    {
      question: 'შემიძლია დავაბრუნო?',
      answer: (
        <p>
          დიახ, მიღებიდან 14 დღის განმავლობაში, თუ პროდუქტი გამოუყენებელია და შეფუთვა დაცულია.
          დეტალები —{' '}
          <Link to={INFO_PAGES.returns.path} className={TEXT_LINK_CLASS}>
            „{INFO_PAGES.returns.title}“
          </Link>{' '}
          გვერდზე.
        </p>
      ),
    },
    {
      question: 'შეკვეთის სტატუსი სად ვნახო?',
      answer: (
        <p>
          რეგისტრირებულს — ანგარიშში,{' '}
          <Link to="/account/orders" className={TEXT_LINK_CLASS}>
            „ჩემი შეკვეთები“
          </Link>
          .
        </p>
      ),
    },
    {
      question: 'პაროლი დამავიწყდა, რა ვქნა?',
      answer: loading ? (
        <Skeleton className="h-5 w-2/3" />
      ) : emailEnabled ? (
        <p>
          შესვლის გვერდზე დააჭირეთ{' '}
          <Link to="/forgot-password" className={TEXT_LINK_CLASS}>
            „დაგავიწყდათ პაროლი?“
          </Link>{' '}
          და მიუთითეთ ანგარიშის ელფოსტა — პაროლის აღდგენის ბმულს გამოგიგზავნით.
        </p>
      ) : (
        // ForgotPassword-ის სიტყვებით. აღდგენას არ ვპირდებით: ადმინ-პანელს
        // მომხმარებლის პაროლის შეცვლა არ შეუძლია
        <p>
          პაროლის აღდგენა ამჟამად მიუწვდომელია. დაგვიკავშირდით ტელეფონით:{' '}
          <a href={CONTACT.phoneHref} className={`whitespace-nowrap ${TEXT_LINK_CLASS}`}>
            {CONTACT.phone}
          </a>
          .
        </p>
      ),
    },
    {
      question: 'როგორ დაგიკავშირდეთ?',
      answer: <ContactList />,
    },
  ];

  return (
    <InfoPage
      page={INFO_PAGES.faq}
      description="პასუხები ხშირ კითხვებზე: შეკვეთა, მიწოდება, გადახდა, დაბრუნება და ანგარიში."
    >
      {items
        .filter((item) => item.answer)
        .map((item) => (
          <InfoSection key={item.question} title={item.question}>
            {item.answer}
          </InfoSection>
        ))}
    </InfoPage>
  );
}
