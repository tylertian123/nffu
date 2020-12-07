import React from 'react';

const UserInfoContext = React.createContext();
const ExtraUserInfoContext = React.createContext();

function UserInfoProvider(props) {
	const [invalidator, setInvalidator] = React.useState();

	const proxyvalue = {
		...window.userinfo,
		invalidate: () => {setInvalidator(!invalidator)}
	};

	return <UserInfoContext.Provider value={proxyvalue}>
		{props.children}
	</UserInfoContext.Provider>;
}

function AdminOnly(props) {
	const userinfo = React.useContext(UserInfoContext);
	if (userinfo.admin) return props.children;
	else return null;
}

function ExtraUserInfoProvider(props) {
	const [extraUserInfo, setEUI] = React.useState(null);
	const [invalidator, setInvalidator] = React.useState(false);

	React.useEffect(() => {
		(async ()=>{
			const response = await fetch("/api/v1/me");
			setEUI(await response.json());
		})();
	}, [invalidator]);

	const obj = extraUserInfo === null ? null : {
		...extraUserInfo,
		invalidate: () => {setInvalidator(!invalidator)}
	};

	return <ExtraUserInfoContext.Provider value={obj}>
		{props.children}
	</ExtraUserInfoContext.Provider>;
}

export { UserInfoProvider, UserInfoContext, AdminOnly, ExtraUserInfoProvider, ExtraUserInfoContext };
