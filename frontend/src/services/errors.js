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
  constructor(message = 'მონაცემები არასწორია', details = null) {
    super(message, 422, details);
    this.name = 'ValidationError';
  }
}

export class AuthError extends ApiError {
  constructor(message = 'ავტორიზაცია ვერ მოხერხდა') {
    super(message, 401);
    this.name = 'AuthError';
  }
}
