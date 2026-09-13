/**
 * Tests for the three form controls, as somebody using a screen reader meets
 * them.
 *
 * The rule: a field that is marked invalid has to say what is wrong. Without
 * `aria-describedby` pointing at the message, a reader announces "invalid" and
 * stops - the sentence explaining why is on screen, unread, a few pixels below.
 * Input already did this; Select and Textarea set `aria-invalid` and left the
 * message unlinked, so "აირჩიეთ კატეგორია" and "სახელი სავალდებულოა" were
 * silent on exactly the fields a form refuses to submit.
 */

import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';

import Input from './Input.jsx';
import Select from './Select.jsx';
import Textarea from './Textarea.jsx';

const OPTIONS = [{ value: 'a', label: 'ერთი' }];

const CONTROLS = [
  ['Input', (props) => <Input label="სახელი" {...props} />, 'textbox'],
  ['Select', (props) => <Select label="კატეგორია" options={OPTIONS} {...props} />, 'combobox'],
  ['Textarea', (props) => <Textarea label="აღწერა" {...props} />, 'textbox'],
];

describe.each(CONTROLS)('%s', (_name, Control, role) => {
  it('is reachable by its label', () => {
    render(<Control onChange={() => {}} value="" />);

    expect(screen.getByRole(role)).toBeInTheDocument();
  });

  it('says it is invalid when it is', () => {
    render(<Control error="არასწორია" onChange={() => {}} value="" />);

    expect(screen.getByRole(role)).toHaveAttribute('aria-invalid', 'true');
  });

  it('points at the message that explains why', () => {
    render(<Control error="სახელი სავალდებულოა" onChange={() => {}} value="" />);

    // toHaveAccessibleDescription resolves aria-describedby the way a screen
    // reader does, so this fails if the id is wrong as well as if it is absent.
    expect(screen.getByRole(role)).toHaveAccessibleDescription('სახელი სავალდებულოა');
  });

  it('points at the hint when there is no error', () => {
    render(<Control hint="ცარიელი — სახელიდან შეიქმნება" onChange={() => {}} value="" />);

    expect(screen.getByRole(role)).toHaveAccessibleDescription('ცარიელი — სახელიდან შეიქმნება');
  });

  it('describes nothing when there is nothing to say', () => {
    render(<Control onChange={() => {}} value="" />);

    expect(screen.getByRole(role)).not.toHaveAttribute('aria-describedby');
  });
});
