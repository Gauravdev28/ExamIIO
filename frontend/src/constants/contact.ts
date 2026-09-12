export const CONTACT_EMAIL = 'gauravagldeveloper28@gmail.com';

export const CONTACT_SUBJECT = 'Inquiry about ExamIIO';

export const CONTACT_BODY = `Hello Gaurav,

I am interested in learning more about ExamIIO and its technical assessment platform.

I would like to discuss:

- Assessment platform capabilities
- Technical evaluation
- Examination supervision
- Potential institutional or commercial use

Please let me know more about the platform and the next steps.

Regards,
[Your Name]`;

// RFC-compliant mailto URI with CRLF encoding for universal mail client support
export const EXAMIIO_CONTACT_MAILTO = `mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent(
  CONTACT_SUBJECT
)}&body=${encodeURIComponent(CONTACT_BODY.replace(/\r?\n/g, '\r\n'))}`;

// Backward-compatible exports
export const VIGILIS_CONTACT_MAILTO = EXAMIIO_CONTACT_MAILTO;
export const EXAMIO_CONTACT_MAILTO = EXAMIIO_CONTACT_MAILTO;
