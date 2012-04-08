int isPrime1(int n) {
  if (n == 2) return 1;
  if (n%2 == 0) return 0;
  int t = 3;
  while (t*t <= n) {
    if ((n%t) == 0) {
      return 0;
    } else {
      t += 2;
    }
  }
  return 1;
}

int modpow(int a, int d, int n) {
  int r = 1;
  int i;
  for (i = 0; i < d; i++) {
    r = (r*a)%n;
  }
  return r;
}

int isPrime2(int n) {
  int nc = n-1;
  int s = 0;
  while ((nc&1) == 0) {
    s += 1;
    nc >>= 1;
  }
  int d = n>>s;
  int a = 2;
  while (a <= 3) {
    if (isPrime1(a)) {
      if (modpow(a,d,n) != 1 & modpow(a,d,n) != n-1) {
	int r = 0;
	int worked = 0;
	while ((r <= s-1) & (r <= s)) {
	  if (modpow(a, (2<<r)*d, n) == n-1) {
	    worked = 1;
	  }
	  r += 1;
	}
	if (worked == 0) {
	  return 0;
	}
      }
    }
    a++;
  }
  return 1;
}


int main() {
  return isPrime2(1003);
}
