import { Fragment, isValidElement } from 'react';
import { t } from './index.js';

/**
 * A translated sentence with elements inside it - a bold amount, a link.
 *
 * `values` may hold React elements as well as plain values. Each element goes
 * in as a marker, the sentence is translated around it, and the markers are
 * swapped back for the elements - so each language puts the link where its own
 * word order wants it, and the element keeps its props and its handlers.
 *
 * Why not react-i18next's <Trans>: this is the one thing the shop would use
 * from it. The language never changes under a running page (index.js), so its
 * subscriptions would have nothing to do.
 */
const MARK = '\u0001';

export default function Rich({ k, values = {} }) {
  const elements = {};
  const options = {};
  for (const [name, value] of Object.entries(values)) {
    if (isValidElement(value)) {
      elements[name] = value;
      options[name] = `${MARK}${name}${MARK}`;
    } else {
      options[name] = value;
    }
  }

  const parts = t(k, options).split(MARK);
  // Odd parts are marker names: "a␁link␁b" → ['a', 'link', 'b'].
  return parts.map((part, index) =>
    index % 2 === 1 && part in elements ? (
      <Fragment key={index}>{elements[part]}</Fragment>
    ) : (
      <Fragment key={index}>{part}</Fragment>
    ),
  );
}
