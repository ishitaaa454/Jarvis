import styles from './SettingsPage.module.css';

const SECTIONS = [
  {
    title: 'Voice',
    description: 'British male TTS profile and speech rate. Read-only in Phase 1.',
  },
  {
    title: 'Wake phrase',
    description: 'Configured phrase: “Wake up, Jarvis.” Detection arrives later.',
  },
  {
    title: 'Welcome message',
    description: 'Spoken greeting lines after wake. Not editable yet.',
  },
  {
    title: 'Workspace applications',
    description: 'Default app launch order for workspace initialization.',
  },
  {
    title: 'Dashboard appearance',
    description: 'Theme density, accent intensity, and layout preferences.',
  },
  {
    title: 'Integrations',
    description: 'Calendar, email, news, and local AI connectors.',
  },
];

export function SettingsPage() {
  return (
    <div className={styles.page}>
      <header>
        <h1 className="page-title">SETTINGS</h1>
        <p className="page-subtitle">Future configuration</p>
      </header>

      <div className={styles.list}>
        {SECTIONS.map((section) => (
          <section key={section.title} className={`glass-panel ${styles.card}`}>
            <h2>{section.title}</h2>
            <p className="muted">{section.description}</p>
            <p className="placeholder-note">Read-only placeholder — Available in a later phase</p>
            <fieldset disabled className={styles.fieldset}>
              <label>
                Value
                <input type="text" value="Not configured" readOnly />
              </label>
            </fieldset>
          </section>
        ))}
      </div>
    </div>
  );
}
