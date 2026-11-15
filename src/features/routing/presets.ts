/**
 * Authored demo prompts. They are examples only; the router decides the tier,
 * so labels never claim a particular outcome.
 */

export interface RoutingPreset {
  id: string;
  label: string;
  text: string;
}

export const ROUTING_PRESETS: RoutingPreset[] = [
  {
    id: 'economy-short',
    label: 'Authored example — a short factual lookup',
    text: 'What is the capital of France?',
  },
  {
    id: 'long-hinglish',
    label: 'Authored example — a long Hinglish word problem',
    text: 'Agar ek train 60 km/h se chalti hai aur doosri 80 km/h se ulti direction se, aur dono 420 km door hain, toh kitne ghante baad milengi? Step by step solve karke batao.',
  },
  {
    id: 'policy-flip',
    label: 'Authored example — a multi-part meeting agenda',
    text: 'Mujhe apni team ke liye ek meeting agenda banana hai jisme product launch, budget review aur hiring plan teeno cover ho, aur total time sirf 45 minute ho. Time slots ke saath batao.',
  },
  {
    id: 'mixed-script',
    label: 'Authored example — a mixed-script resume request',
    text: 'Please मेरे resume का summary rewrite करो so that it sounds more senior, और बताओ कि कौन से 3 skills add करने चाहिए data analyst role के लिए।',
  },
  {
    id: 'known-weak',
    label: 'Authored example — a known weak case',
    text: 'Mere paas teen options hain: FD, mutual fund SIP aur PPF. Main 30 saal ka hoon, mahine ke 15000 invest kar sakta hoon aur 15 saal ka horizon hai. In teeno ko risk, return aur tax ke hisaab se compare karke batao ki mujhe paisa kaise baantna chahiye.',
  },
];
