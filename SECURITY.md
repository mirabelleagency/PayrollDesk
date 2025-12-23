# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 2.x.x   | :white_check_mark: |
| 1.x.x   | :x:                |

## Reporting a Vulnerability

We take security seriously at PayrollDesk. If you discover a security vulnerability, please follow these guidelines:

### Do NOT

- Open a public GitHub issue for security vulnerabilities
- Disclose the vulnerability publicly before it has been addressed
- Exploit the vulnerability beyond what is necessary to demonstrate it

### Do

1. **Email us directly** at [security contact - add your email here]
2. **Include details** such as:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

### What to Expect

- **Acknowledgment**: We will acknowledge receipt within 48 hours
- **Assessment**: We will assess the vulnerability within 5 business days
- **Resolution**: Critical issues will be prioritized for immediate fix
- **Credit**: We will credit reporters in our changelog (unless you prefer anonymity)

## Security Best Practices

### For Developers

1. **Never commit secrets** - Use environment variables
2. **Keep dependencies updated** - Run `pip-audit` regularly
3. **Use parameterized queries** - SQLAlchemy ORM handles this
4. **Validate all inputs** - Use Pydantic schemas
5. **Hash passwords** - We use bcrypt

### For Administrators

1. **Use strong passwords** - Minimum 12 characters
2. **Enable HTTPS** - Required in production
3. **Restrict database access** - Use least privilege
4. **Monitor logs** - Watch for suspicious activity
5. **Regular backups** - Test restoration procedures

## Security Features

### Authentication

- Session-based authentication with secure cookies
- Password hashing with bcrypt
- Login attempt limiting (configurable)
- Session timeout

### Data Protection

- All database queries use SQLAlchemy ORM (SQL injection protection)
- Input validation via Pydantic schemas
- HTTPS enforcement in production
- Sensitive data not logged

### Access Control

- Role-based access (admin/user)
- Route protection via dependencies
- Admin-only features isolated

## Known Security Considerations

### Development Mode

In development mode (`ENVIRONMENT=development`), the following relaxed security settings may apply:
- SQLite fallback enabled
- Debug logging may be more verbose

**Never use development settings in production.**

### Database Credentials

- PostgreSQL connection strings contain credentials
- Use environment variables, never commit to code
- Use Render's secret management for production

## Audit Log

Security-related changes are tracked in the [CHANGELOG.md](CHANGELOG.md).

---

*Last updated: December 2025*
