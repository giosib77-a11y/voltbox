/** API-ს შეცდომების ერთიანი იერარქია — mock და http იმპლემენტაციებისთვის საერთო. */

export class ApiError extends Error {
  constructor(message, status = 500, details = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.details = details;
  }
}

export class NotFoundError extends ApiError {
  constructor(message = 'მოთხოვნილი ჩანაწერი ვერ მოიძებნა') {
    super(message, 404);
    this.name = 'NotFoundError';
  }
}

export class ValidationError extends ApiError {
  // სტატუსი პარამეტრია, რადგან ეს API ვალიდაციაზე 400-ს აბრუნებს და არა 422-ს
  // (იხ. backend `register_exception_handlers`). ჩაწერილი 422 ტყუილი იქნებოდა.
  constructor(message = 'მონაცემები არასწორია', details = null, status = 400) {
    super(message, status, details);
    this.name = 'ValidationError';
  }
}

export class AuthError extends ApiError {
  // 401 („ვინ ხარ?“) და 403 („ვიცი ვინც ხარ, მაგრამ არ გიშვებ“) სხვადასხვა
  // რეაქციას ითხოვს: პირველზე შესვლის გვერდი, მეორეზე — უარის ახსნა.
  // ამიტომ სტატუსი რეალურია და არა ჩაწერილი.
  constructor(message = 'ავტორიზაცია ვერ მოხერხდა', status = 401, details = null) {
    super(message, status, details);
    this.name = 'AuthError';
  }
}

/** 409 — უნიკალურობის ან მდგომარეობის კონფლიქტი (SKU, slug, მარაგი, სტატუსი). */
export class ConflictError extends ApiError {
  constructor(message = 'ოპერაცია ეწინააღმდეგება არსებულ მონაცემებს', details = null) {
    super(message, 409, details);
    this.name = 'ConflictError';
  }
}
