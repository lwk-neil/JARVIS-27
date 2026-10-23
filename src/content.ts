export const navigation = [
  { label: 'Features', href: '#features' },
  { label: 'How it works', href: '#how-it-works' },
  { label: 'Your control', href: '#control' },
  { label: 'FAQ', href: '#faq' },
]

export const features = [
  {
    number: '01',
    icon: 'wave',
    title: 'A conversation, not a command line',
    description:
      'Talk naturally, hear responses aloud, and keep the thread moving while SYKE works through a task.',
    tag: 'VOICE, BUILT IN',
    className: 'feature-card--voice',
  },
  {
    number: '02',
    icon: 'key',
    title: 'Your mic, on your terms',
    description:
      'Hold Ctrl to speak with push-to-talk, or configure the optional local “Hey Jarvis” wake word.',
    tag: 'HOLD CTRL TO TALK',
    className: '',
  },
  {
    number: '03',
    icon: 'spark',
    title: 'A little life in the interface',
    description:
      'A drifting point-cloud sphere reacts to the assistant, with live color protocols you can change by voice.',
    tag: 'LIVE VISUALS',
    className: '',
  },
  {
    number: '04',
    icon: 'window',
    title: 'Fits the way you work',
    description:
      'Use desktop actions and app controls that are available to your operating system and enabled permissions.',
    tag: 'DESKTOP COMPANION',
    className: '',
  },
  {
    number: '05',
    icon: 'nodes',
    title: 'Choose the intelligence behind it',
    description:
      'Use the Gemini Live experience, or configure a supported hosted provider or local model for other tasks.',
    tag: 'YOUR ENGINE, YOUR CHOICE',
    className: '',
  },
  {
    number: '06',
    icon: 'shield',
    title: 'Clear about what it can do',
    description:
      'SYKE’s reach depends on your setup, provider, OS permissions, and confirmation settings—not a promise of unrestricted access.',
    tag: 'PERMISSIONS MATTER',
    className: '',
  },
]

export const steps = [
  {
    number: '01',
    title: 'Set up your space',
    description:
      'Install SYKE, add the credentials for your chosen AI service, and pick your audio devices.',
  },
  {
    number: '02',
    title: 'Make it yours',
    description:
      'Choose push-to-talk or configure wake word, then select an available engine and the permissions you want to grant.',
  },
  {
    number: '03',
    title: 'Say what you need',
    description:
      'Speak naturally. Hold Ctrl for push-to-talk, or use the configured wake word when that option is enabled.',
  },
]

export const controlPoints = [
  {
    label: 'Microphone',
    title: 'You choose when it listens',
    description:
      'Push-to-talk keeps the mic closed until Ctrl is held. Wake-word mode is optional and can be switched off.',
    number: '01',
  },
  {
    label: 'Providers',
    title: 'Know where requests go',
    description:
      'Audio and text handling depend on the selected engine. Configure local models when you want a local pipeline; hosted providers process data on their own services.',
    number: '02',
  },
  {
    label: 'Permissions',
    title: 'The operating system sets limits',
    description:
      'Desktop actions work only where the OS permits them. Sensitive actions may require confirmation, and access is not unrestricted.',
    number: '03',
  },
]

export const faqs = [
  {
    question: 'Which platforms does SYKE support?',
    answer:
      'The desktop app targets Windows, macOS, and Linux. Individual actions and permission requirements vary by operating system.',
  },
  {
    question: 'How does Ctrl push-to-talk work?',
    answer:
      'When push-to-talk is enabled, hold Ctrl while speaking and release it when you are done. The global shortcut is available on Windows; on macOS and Linux it works while the SYKE window has focus.',
  },
  {
    question: 'Do I need to use a wake word?',
    answer:
      'No. Wake-word support is optional. You can use push-to-talk instead, or leave both off and use the other configured input methods.',
  },
  {
    question: 'Can I use a local AI model?',
    answer:
      'The app supports configuring local model endpoints for supported tasks, as well as hosted providers. Which features work depends on the engine you choose and configure.',
  },
  {
    question: 'Does SYKE have unrestricted access to my computer?',
    answer:
      'No. Available actions are limited by your configuration, operating system permissions, and confirmation settings. Some actions may require additional OS permissions.',
  },
]

export const footerLinks = [
  { label: 'Documentation', href: '#how-it-works' },
  { label: 'FAQ & support', href: '#faq' },
  { label: 'Permissions', href: '#control' },
]
