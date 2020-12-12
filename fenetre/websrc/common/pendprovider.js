import React from 'react';

import "regenerator-runtime/runtime";

// Callback should be async
function useBackoffEffect(callback, deps) {
	const backoffs = [2500, 5000, 10000, 30000];
	const [backoffLevel, setBackoffLevel] = React.useState(0);
	const backoffIdx = (backoffLevel / 5) | 0; // integer divide, try each level 5 times.
	const currentBackoffDelay = backoffs[backoffIdx >= backoffs.size ? backoffs.size-1 : backoffIdx];

	React.useEffect(() => {
		let isGone = false;

		if (backoffLevel == -1) {
			return;
		}

		(async ()=>{
			if (await callback() && !isGone) {
				setTimeout(()=>{if (!isGone) setBackoffLevel(backoffLevel+1)}, currentBackoffDelay);
			}
			else {
				setBackoffLevel(-1);
			}
		})();

		return () => {
			isGone = true;
		}
	}, [backoffLevel]);

	React.useEffect(() => {
		if (backoffLevel) setBackoffLevel(0);
	}, deps);

	return () => setBackoffLevel(0);
}

export default useBackoffEffect;
