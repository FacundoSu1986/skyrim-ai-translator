export function DragonMedallion() {
  return (
    <div className="dragon-medallion-wrapper">
      <svg
        className="dragon-sigil"
        viewBox="0 0 200 200"
        role="img"
        aria-label="Emblema del Dragón de Skyrim Translator"
      >
        <defs>
          {/* Metal Gradients */}
          <linearGradient id="medallionRim" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#fff6d6" />
            <stop offset="20%" stopColor="#d5ae5d" />
            <stop offset="50%" stopColor="#7a551b" />
            <stop offset="75%" stopColor="#3d290b" />
            <stop offset="100%" stopColor="#9a7330" />
          </linearGradient>

          <linearGradient id="ironPlate" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#1a2530" />
            <stop offset="50%" stopColor="#0d141b" />
            <stop offset="100%" stopColor="#06090d" />
          </linearGradient>

          <linearGradient id="dragonBodyMetal" x1="0%" y1="0%" x2="100%" y2="90%">
            <stop offset="0%" stopColor="#ffffff" />
            <stop offset="25%" stopColor="#dce8f0" />
            <stop offset="55%" stopColor="#8da0af" />
            <stop offset="75%" stopColor="#dfb758" />
            <stop offset="100%" stopColor="#3b4854" />
          </linearGradient>

          <radialGradient id="frostGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#6fe3ff" stopOpacity="0.45" />
            <stop offset="50%" stopColor="#2da1d4" stopOpacity="0.18" />
            <stop offset="100%" stopColor="#080d12" stopOpacity="0" />
          </radialGradient>

          <filter id="sigilShadow" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="6" stdDeviation="6" floodColor="#000000" floodOpacity="0.9" />
          </filter>

          <filter id="eyeGlow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="2" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Outer Bezel & Shadow */}
        <circle cx="100" cy="100" r="94" fill="url(#ironPlate)" stroke="url(#medallionRim)" strokeWidth="3" filter="url(#sigilShadow)" />
        
        {/* Concentric Relief Rings */}
        <circle cx="100" cy="100" r="86" fill="none" stroke="#2a3a49" strokeWidth="1.5" />
        <circle cx="100" cy="100" r="82" fill="#090e13" stroke="url(#medallionRim)" strokeWidth="1" strokeDasharray="6 3" opacity="0.8" />
        
        {/* Magic Frost Ambient Aura behind Dragon */}
        <circle cx="100" cy="105" r="70" fill="url(#frostGlow)" />

        {/* Runic Calendar Ring (Elder Futhark Accents) */}
        <g className="sigil-runes" stroke="url(#medallionRim)" strokeWidth="1.6" strokeLinecap="round" opacity="0.75">
          {/* 12 Cardinal Rune Hash Marks */}
          <line x1="100" y1="9" x2="100" y2="16" />
          <line x1="145" y1="21" x2="141" y2="28" />
          <line x1="179" y1="55" x2="172" y2="59" />
          <line x1="191" y1="100" x2="184" y2="100" />
          <line x1="179" y1="145" x2="172" y2="141" />
          <line x1="145" y1="179" x2="141" y2="172" />
          <line x1="100" y1="191" x2="100" y2="184" />
          <line x1="55" y1="179" x2="59" y2="172" />
          <line x1="21" y1="145" x2="28" y2="141" />
          <line x1="9" y1="100" x2="16" y2="100" />
          <line x1="21" y1="55" x2="28" y2="59" />
          <line x1="55" y1="21" x2="59" y2="28" />

          {/* Tiny Rune Symbols on Bezel */}
          <path d="M 98 18 L 102 18 M 100 18 L 100 24" />
          <path d="M 174 98 L 180 100 L 174 102" />
          <path d="M 20 98 L 26 100 L 20 102" />
        </g>

        {/* Nordic Dragon Crest (Stylized Original High-Detail Relief) */}
        {/* Wing & Crest Plates */}
        <path
          fill="url(#dragonBodyMetal)"
          stroke="#101820"
          strokeWidth="0.8"
          d="M 132 38
             C 120 42, 110 49, 100 58
             C 90 49, 76 45, 60 50
             C 68 56, 75 63, 80 72
             C 67 73, 56 80, 48 90
             C 60 88, 70 90, 78 97
             C 60 106, 50 120, 46 140
             C 58 128, 70 122, 84 122
             C 70 136, 66 152, 70 172
             C 76 158, 86 148, 98 140
             C 98 154, 94 168, 86 181
             C 104 172, 116 158, 124 138
             C 130 122, 130 106, 125 90
             C 135 80, 142 66, 144 50
             C 135 58, 126 63, 116 64
             C 126 54, 131 44, 132 38 Z"
        />

        {/* Secondary Wing Inlay (Layered Feather Ribs) */}
        <path
          fill="#1c2b38"
          opacity="0.65"
          d="M 100 72
             C 114 62, 128 60, 142 65
             C 134 68, 126 73, 120 80
             C 126 82, 132 87, 136 94
             C 122 90, 110 93, 100 100
             C 102 90, 102 80, 100 72 Z"
        />

        {/* Dragon Spine & Head Carving */}
        <path
          fill="url(#dragonBodyMetal)"
          d="M 98 42 L 104 54 L 100 68 L 106 82 L 100 96 L 104 110 L 98 125 L 94 110 L 98 96 L 92 82 L 98 68 Z"
          opacity="0.9"
        />

        {/* Glowing Sapphire Dragon Eye */}
        <polygon
          points="114,75 124,78 117,83 110,80"
          fill="#d0f6ff"
          filter="url(#eyeGlow)"
        />
        <circle cx="116" cy="79" r="1.5" fill="#ffffff" />

        {/* Serpentine Lower Tail Knot */}
        <path
          d="M 100 122
             C 80 128, 68 142, 64 162
             C 78 152, 92 150, 106 154
             C 98 159, 94 166, 90 176
             C 110 168, 124 154, 132 134"
          fill="none"
          stroke="url(#medallionRim)"
          strokeWidth="3.5"
          strokeLinecap="round"
        />

        {/* Bottom Base Rune Keystone (Diamond Inlay) */}
        <g transform="translate(100, 168)">
          <polygon points="0,-10 10,0 0,10 -10,0" fill="#0a1822" stroke="url(#medallionRim)" strokeWidth="1.5" />
          <polygon points="0,-6 6,0 0,6 -6,0" fill="#176c94" stroke="#6fe3ff" strokeWidth="1" filter="url(#eyeGlow)" />
        </g>
      </svg>
    </div>
  );
}

export default DragonMedallion;
