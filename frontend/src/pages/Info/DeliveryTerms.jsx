import { INFO_PAGES } from '../../constants/index.js';
import { t } from '../../i18n/index.js';
import InfoPage, { InfoSection } from './InfoPage.jsx';
import DeliveryTable from './DeliveryTable.jsx';

/**
 * მიწოდების პირობები — ქალაქები და ფასები `GET /delivery`-დან.
 *
 * The words are all under `info.delivery` in ka.json and en.json, so a change
 * of courier - the terms, the time - is made there and nowhere else. The time
 * itself is `shipping.etaDays`, the one the cart shows.
 */
export default function DeliveryTerms() {
  return (
    <InfoPage page={INFO_PAGES.delivery} description={t('info.delivery.description')}>
      <InfoSection title={t('info.delivery.whereTitle')}>
        <p>{t('info.delivery.whereText')}</p>
      </InfoSection>

      <InfoSection title={t('info.delivery.costTitle')}>
        <DeliveryTable />
        <p>{t('info.delivery.costNote')}</p>
      </InfoSection>

      <InfoSection title={t('info.delivery.timeTitle')}>
        <p>{t('info.delivery.timeText', { eta: t('shipping.etaDays') })}</p>
      </InfoSection>

      <InfoSection title={t('info.delivery.paymentTitle')}>
        <p>{t('info.delivery.paymentText')}</p>
      </InfoSection>

      <InfoSection title={t('info.delivery.receiptTitle')}>
        <p>{t('info.delivery.receiptText')}</p>
      </InfoSection>
    </InfoPage>
  );
}
