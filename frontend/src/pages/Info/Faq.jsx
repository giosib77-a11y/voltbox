import { Link } from 'react-router';
import { Skeleton } from '../../components/common/Skeleton.jsx';
import { CONTACT, INFO_PAGES } from '../../constants/index.js';
import { t } from '../../i18n/index.js';
import Rich from '../../i18n/Rich.jsx';
import { useDeliveryRules } from '../../hooks/useDeliveryRules.js';
import { useEmailEnabled } from '../../hooks/useEmailEnabled.js';
import InfoPage, { InfoSection, TEXT_LINK_CLASS } from './InfoPage.jsx';
import DeliveryTable from './DeliveryTable.jsx';
import { ContactList } from './Contact.jsx';

/**
 * ხშირად დასმული კითხვები.
 *
 * „შეკვეთის სტატუსი“ მხოლოდ რეგისტრირებულს პასუხობს: სტუმარს საიტზე
 * შეკვეთის მოსაძებნი გვერდი არ აქვს — იხ. docs/info-pages-todo.md.
 *
 * A link's text is the title of the page or control it leads to (`nav.orders`,
 * `auth.forgot`), so the FAQ names it as that page does, in either language.
 */
export default function Faq() {
  const { rules, loading } = useDeliveryRules();
  const emailEnabled = useEmailEnabled();

  const quoted = (text) => t('info.common.quoted', { text });

  const items = [
    {
      question: t('info.faq.orderQuestion'),
      answer: <p>{t('info.faq.orderAnswer')}</p>,
    },
    {
      question: t('info.faq.registrationQuestion'),
      answer: <p>{t('info.faq.registrationAnswer')}</p>,
    },
    {
      question: t('info.faq.costQuestion'),
      answer: <DeliveryTable />,
    },
    {
      question: t('info.faq.whereQuestion'),
      answer: (
        <p>
          {t('info.faq.whereAnswer', {
            cities: rules ? `: ${rules.cities.map((city) => city.name).join(', ')}` : '',
          })}
        </p>
      ),
    },
    {
      question: t('info.faq.payQuestion'),
      answer: <p>{t('info.faq.payAnswer')}</p>,
    },
    {
      question: t('info.faq.timeQuestion'),
      answer: <p>{t('info.faq.timeAnswer', { eta: t('shipping.etaDays') })}</p>,
    },
    {
      question: t('info.faq.returnQuestion'),
      answer: (
        <p>
          <Rich
            k="info.faq.returnAnswer"
            values={{
              link: (
                <Link to={INFO_PAGES.returns.path} className={TEXT_LINK_CLASS}>
                  {quoted(t(INFO_PAGES.returns.titleKey))}
                </Link>
              ),
            }}
          />
        </p>
      ),
    },
    {
      question: t('info.faq.statusQuestion'),
      answer: (
        <p>
          <Rich
            k="info.faq.statusAnswer"
            values={{
              link: (
                <Link to="/account/orders" className={TEXT_LINK_CLASS}>
                  {quoted(t('nav.orders'))}
                </Link>
              ),
            }}
          />
        </p>
      ),
    },
    {
      question: t('info.faq.passwordQuestion'),
      answer: loading ? (
        <Skeleton className="h-5 w-2/3" />
      ) : emailEnabled ? (
        <p>
          <Rich
            k="info.faq.passwordAnswerOn"
            values={{
              link: (
                <Link to="/forgot-password" className={TEXT_LINK_CLASS}>
                  {quoted(t('auth.forgot'))}
                </Link>
              ),
            }}
          />
        </p>
      ) : (
        // ForgotPassword-ის სიტყვებით. აღდგენას არ ვპირდებით: ადმინ-პანელს
        // მომხმარებლის პაროლის შეცვლა არ შეუძლია
        <p>
          <Rich
            k="info.faq.passwordAnswerOff"
            values={{
              phone: (
                <a href={CONTACT.phoneHref} className={`whitespace-nowrap ${TEXT_LINK_CLASS}`}>
                  {CONTACT.phone}
                </a>
              ),
            }}
          />
        </p>
      ),
    },
    {
      question: t('info.faq.contactQuestion'),
      answer: <ContactList />,
    },
  ];

  return (
    <InfoPage page={INFO_PAGES.faq} description={t('info.faq.description')}>
      {items.map((item) => (
        <InfoSection key={item.question} title={item.question}>
          {item.answer}
        </InfoSection>
      ))}
    </InfoPage>
  );
}
