const leftptr = `
<svg width="25px" height="25px" viewBox="0 0 200 200" fill="none" xmlns="http://www.w3.org/2000/svg">
<g clip-path="url(#clip0_1782_16)">
<g filter="url(#filter0_d_1782_16)">
<path fill-rule="evenodd" clip-rule="evenodd" d="M51 147V7L152 108.571H92.9127L89.3314 109.655L51 147Z" fill="#FFFFFF"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M129 152.644L97.6787 166L57 69.5129L89.0251 56L129 152.644Z" fill="#FFFFFF"/>
</g>
<path fill-rule="evenodd" clip-rule="evenodd" d="M118 146.256L101.589 153L74 88.7524L90.3843 82L118 146.256Z" fill="#000000"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M59 28V125L84.8174 100.152L88.5391 98.9466H130L59 28Z" fill="#000000"/>
</g>
<defs>
<filter id="filter0_d_1782_16" x="33" y="-1" width="131" height="189" filterUnits="userSpaceOnUse" color-interpolation-filters="sRGB">
<feFlood flood-opacity="0" result="BackgroundImageFix"/>
<feColorMatrix in="SourceAlpha" type="matrix" values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 127 0" result="hardAlpha"/>
<feOffset dx="-3" dy="7"/>
<feGaussianBlur stdDeviation="7.5"/>
<feColorMatrix type="matrix" values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0.3 0"/>
<feBlend mode="normal" in2="BackgroundImageFix" result="effect1_dropShadow_1782_16"/>
<feBlend mode="normal" in="SourceGraphic" in2="effect1_dropShadow_1782_16" result="shape"/>
</filter>
<clipPath id="clip0_1782_16">
<rect width="200" height="200" fill="white"/>
</clipPath>
</defs>
</svg>
`;

window.addEventListener(
  "DOMContentLoaded",
  () => {
    const box = document.createElement("p-mouse-pointer");
    box.innerHTML = leftptr;
    const styleElement = document.createElement("style");
    styleElement.innerHTML = `
  p-mouse-pointer {
      pointer-events: none;
      position: absolute;
      top: 0;
      z-index: 10000;
      left: 0;
      width: 20px;
      height: 20px;
  }
  p-mouse-pointer.button-1 {
      transition: none;
      border-radius: 50%;
      border: 4px solid rgba(0,0,255,0.9);
  }
  p-mouse-pointer.button-2 {
      transition: none;
      border-color: rgba(0,0,255,0.9);
  }
  p-mouse-pointer.button-3 {
      transition: none;
      border-radius: 4px;
  }
  p-mouse-pointer.button-4 {
      transition: none;
      border-color: rgba(255,0,0,0.9);
  }
  p-mouse-pointer.button-5 {
      transition: none;
      border-color: rgba(0,255,0,0.9);
  }
  p-mouse-pointer-hide {
      display: none
  }
  `;
    document.head.appendChild(styleElement);
    document.body.appendChild(box);
    document.addEventListener(
      "mousemove",
      (event) => {
        box.style.left = String(event.pageX) + "px";
        box.style.top = String(event.pageY) + "px";
        box.classList.remove("p-mouse-pointer-hide");
        updateButtons(event.buttons);
      },
      true
    );
    document.addEventListener(
      "mousedown",
      (event) => {
        updateButtons(event.buttons);
        box.classList.add("button-" + String(event.which));
        box.classList.remove("p-mouse-pointer-hide");
      },
      true
    );
    document.addEventListener(
      "mouseup",
      (event) => {
        updateButtons(event.buttons);
        box.classList.remove("button-" + String(event.which));
        box.classList.remove("p-mouse-pointer-hide");
      },
      true
    );
    document.addEventListener(
      "mouseleave",
      (event) => {
        updateButtons(event.buttons);
        box.classList.add("p-mouse-pointer-hide");
      },
      true
    );
    document.addEventListener(
      "mouseenter",
      (event) => {
        updateButtons(event.buttons);
        box.classList.remove("p-mouse-pointer-hide");
      },
      true
    );
    /* eslint-disable */
    function updateButtons(buttons) {
      for (let i = 0; i < 5; i++) {
        // @ts-ignore
        box.classList.toggle("button-" + String(i), buttons & (1 << i));
      }
    }
  },
  false
);
