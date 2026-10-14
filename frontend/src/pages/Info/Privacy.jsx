import { INFO_PAGES, SHOP_FACTS } from '../../constants/index.js';
import { useEmailEnabled } from '../../hooks/useEmailEnabled.js';
import { t } from '../../i18n/index.js';
import Rich from '../../i18n/Rich.jsx';
import InfoPage, { InfoSection } from './InfoPage.jsx';
import { ContactInline } from './Contact.jsx';

/**
 * კონფიდენციალურობის პოლიტიკა.
 *
 * ყოველი მტკიცება კოდს ემთხვევა და InfoPages.test.jsx ამას ამოწმებს:
 * რა ინახება ბრაუზერში (STORAGE_KEYS, services/httpApi.js-ის
 * GUEST_ORDERS_KEY), რა მიდის Telegram-ში (backend/app/services/telegram.py),
 * რას ითხოვს რეგისტრაცია. ერთ მხარეს ცვლილება მეორესაც მოითხოვს.
 * The test reads the Georgian text; the English is the same sentences, one
 * for one (`info.privacy` in en.json), so a change here is made in both.
 *
 * Resend სიაში მხოლოდ მაშინ ჩანს, როცა მაღაზია წერილს მართლა აგზავნის
 * (`useEmailEnabled`) — მანამდე მას მყიდველის არცერთი მონაცემი არ ეგზავნება.
 */
export default function Privacy() {
  const emailEnabled = useEmailEnabled();
  const { legalEntity } = SHOP_FACTS;

  return (
    <InfoPage page={INFO_PAGES.privacy} description={t('info.privacy.description')}>
      {legalEntity && (
        <InfoSection title={t('info.privacy.whoTitle')}>
          <dl className="grid gap-x-4 gap-y-1.5 sm:grid-cols-[auto_1fr]">
            <dt className="font-semibold text-ink-900">{t('info.privacy.whoName')}</dt>
            <dd>{legalEntity.name}</dd>
            <dt className="font-semibold text-ink-900">{t('info.privacy.whoIdCode')}</dt>
            <dd>{legalEntity.idCode}</dd>
            <dt className="font-semibold text-ink-900">{t('info.privacy.whoAddress')}</dt>
            <dd>{legalEntity.address}</dd>
          </dl>
        </InfoSection>
      )}

      <InfoSection title={t('info.privacy.collectTitle')}>
        <p>
          <strong className="font-semibold text-ink-900">{t('info.privacy.collectOrderLabel')}</strong>{' '}
          {t('info.privacy.collectOrder')}
        </p>
        <p>
          <strong className="font-semibold text-ink-900">
            {t('info.privacy.collectAccountLabel')}
          </strong>{' '}
          {t('info.privacy.collectAccount')}
        </p>
        <p>
          <strong className="font-semibold text-ink-900">{t('info.privacy.collectTechLabel')}</strong>{' '}
          {t('info.privacy.collectTech')}
        </p>
      </InfoSection>

      <InfoSection title={t('info.privacy.useTitle')}>
        <p>{t('info.privacy.useText')}</p>
      </InfoSection>

      <InfoSection title={t('info.privacy.shareTitle')}>
        <p>{t('info.privacy.shareIntro')}</p>
        <ul className="list-disc space-y-1.5 pl-5">
          <li>{t('info.privacy.shareCourier')}</li>
          <li>{t('info.privacy.shareRender')}</li>
          <li>{t('info.privacy.shareSupabase')}</li>
          {emailEnabled && <li>{t('info.privacy.shareResend')}</li>}
        </ul>
        <p>{t('info.privacy.shareInternal')}</p>
      </InfoSection>

      <InfoSection title={t('info.privacy.browserTitle')}>
        <p>{t('info.privacy.browserText')}</p>
      </InfoSection>

      <InfoSection title={t('info.privacy.retentionTitle')}>
        <p>{t('info.privacy.retentionText')}</p>
      </InfoSection>

      <InfoSection title={t('info.privacy.rightsTitle')}>
        <p>
          <Rich k="info.privacy.rightsText" values={{ contact: <ContactInline /> }} />
        </p>
      </InfoSection>
    </InfoPage>
  );
}
