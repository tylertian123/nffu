import React from 'react';

const UserInfoContext = React.createContext();
const AdminStateContext = React.createContext();

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

export { UserInfoProvider, UserInfoContext, AdminOnly };
